import xml.etree.ElementTree as ET 
import json
#from json2xml import json2xml
import xmltodict
from datetime import datetime
import uuid
#with open('rsm.json', 'r') as f:


def wzdx_creator(message):
    RSM = message['MessageFrame']['value']['RoadsideSafetyMessage']
    wzd = {}
    wzd['road_event_feed_info'] = {}
    wzd['road_event_feed_info']['feed_update_date'] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    #wzd['road_event_feed_info']['metadata'] = 'https://fake-site.ltd/dummy-metadata.txt'
    wzd['road_event_feed_info']['version'] = '2.0'
    wzd['type'] = 'FeatureCollection'
    wzd['features'] = wzdx_collapser(extract_nodes(RSM))
    return wzd

def wzdx_collapser(features): #Collapse identical nodes together to reduce overall number of nodes
    #return features
    new_nodes = []
    new_nodes.append(features[0])
    directions = []
    for i in range(1, len(features)):
        new_nodes[-1]['geometry']['coordinates'].append(features[i]['geometry']['coordinates'][0]) #Add coordinates of next node to end of previous node
        if features[i]['properties'] != features[i-1]['properties'] and i != len(features)-1: #Only add unique nodes to output list
            new_nodes.append(features[i])
    long_dif = new_nodes[-1]['geometry']['coordinates'][-1][0] - new_nodes[0]['geometry']['coordinates'][0][0]
    lat_dif = new_nodes[-1]['geometry']['coordinates'][-1][1] - new_nodes[0]['geometry']['coordinates'][0][1]
    if abs(long_dif) > abs(lat_dif):
        if long_dif > 0:
            direction = 'eastbound'
        else:
            direction = 'westbound'
    elif lat_dif > 0:
        direction = 'northbound'
    else:
        direction = 'southbound'
    for i in range(len(new_nodes)):
        new_nodes[i]['properties']['direction'] = direction

    
    return new_nodes

def form_len(string):
    num = int(string)
    return format(num, '02d')

def extract_nodes(RSM):
    lanes = RSM['rszContainer']['rszRegion']['roadwayGeometry']['rsmLanes']['RSMLane']
    num_lanes = len(lanes)
    nodes = lanes[0]['laneGeometry']['nodeSet']['NodeLLE']
    nodes_wzdx = []
    prev_attr_list = []
    for k in range(len(lanes)):
        prev_attributes = {'laneClosed': False, 'peoplePresent': False}
        prev_attr_list.append(prev_attributes)
    for i in range(len(nodes)):
        lanes_obj = {}
        lanes_wzdx = []
        reduced_speed_limit = RSM['commonContainer']['regionInfo']['speedLimit']['speed'] #Assume in mph and max speed limit
        if RSM['commonContainer']['regionInfo']['speedLimit']['speedUnits'].get('kph', {}) == None: #If kph, convert to mph
            reduced_speed_limit = round(reduced_speed_limit*0.6214)
        people_present = False #initialization
        geometry = {}
        geometry['type'] = 'LineString'
        for j in range(len(lanes)):
            lane = {}
            #lane['lane_id'] = lanes[j]['laneID']
            #lane['road_event_id'] = ''
            lane['lane_number'] = int(lanes[j]['lanePosition'])
            lane['lane_edge_reference'] = 'left' #This is an assumed value
            lane_type = 'middle-lane' #left-lane, right-lane, middle-lane, right-exit-lane, left-exit-lane, ... (exit lanes, merging lanes, turning lanes)
            if lane['lane_edge_reference'] == 'left':
                if lane['lane_number'] == 1:
                    lane_type = 'left-lane'
                elif lane['lane_number'] == num_lanes:
                    lane_type = 'right-lane'
            elif lane['lane_edge_reference'] == 'right':
                if lane['lane_number'] == 1:
                    lane_type = 'right-lane'
                elif lane['lane_number'] == num_lanes:
                    lane_type = 'left-lane'
            lane['lane_type'] = lane_type
            #lane['lane_description'] = lanes[j]['laneName']
            node_contents = lanes[j]['laneGeometry']['nodeSet']['NodeLLE'][i]
            lane_status = 'open' #Can be open, closed, shift-left, shift-right, merge-right, merge-left, alternating-one-way

            if node_contents.get('nodeAttributes', {}).get('taperLeft', {}).get('true', {}) == None:
                lane_status = 'merge-left'
            elif node_contents.get('nodeAttributes', {}).get('taperRight', {}).get('true', {}) == None:
                lane_status = 'merge-right'

            if node_contents.get('nodeAttributes', {}).get('laneClosed', {}).get('true', {}) == None: #laneClosed set to true, set lane_status to closed and previous value
                lane_status = 'closed'
                prev_attr_list[j]['laneClosed'] = True
            elif node_contents.get('nodeAttributes', {}).get('laneClosed', {}).get('false', {}) == None: #laneClosed set to false, leave lane_status alone and set previous value
                prev_attr_list[j]['laneClosed'] = False
            elif prev_attr_list[j]['laneClosed']: #No info in current node, use previous value
                lane_status = 'closed'


            lane['lane_status'] = lane_status
            point = lanes[j]['laneGeometry']['nodeSet']['NodeLLE'][i]['nodePoint']
            if lane['lane_number'] == 1:
                lane_coordinate = []
                if point.get('node-3Dabsolute') is not None: #Store coordinates of node for use later
                    lane_coordinate.append(int(point['node-3Dabsolute']['long'])/10000000)
                    lane_coordinate.append(int(point['node-3Dabsolute']['lat'])/10000000)
                else: #Node is defined as offset (node-3Doffset), this is not yet supported
                    lane_coordinate.append(0)
                    lane_coordinate.append(0)
                geometry['coordinates'] = []
                geometry['coordinates'].append(lane_coordinate)
            
            #lane['lane_restrictions'] = []#no-trucks, travel-peak-hours-only, hov-3, hov-2, no-parking
                #reduced-width, reduced-height, reduced-length, reduced-weight, axle-load-limit, gross-weight-limit, towing-prohibited, permitted-oversize-loads-prohibited
            # Restrictions will be added later
            #if restr['restriction_type'] in ['reduced-width', 'reduced-height', 'reduced-length', 'reduced-weight', 'axle-load-limit', 'gross-weight-limit']:
            #    restr['restriction_value'] = restriction['restriction_value']
            #    restr['restriction_units'] = restriction['restriction_units']
            #for lane_restriction in 

            # Reduced Speed Limit
            if node_contents.get('nodeAttributes', {}).get('speedLimit', {}).get('type', {}).get('vehicleMaxSpeed', {}) == None:
                reduced_speed_limit = int(node_contents['nodeAttributes']['speedLimit']['speed'])
                units = node_contents['nodeAttributes']['speedLimit']['speedUnits']
                if units.get('kph', {}) == None:
                    reduced_speed_limit = round(reduced_speed_limit*0.6214)

            if node_contents.get('nodeAttributes', {}).get('peoplePresent', {}).get('true', {}) == None: #People present
                people_present = True
            elif node_contents.get('nodeAttributes', {}).get('peoplePresent', {}).get('false', {}) == None: #No people present
                people_present = False
            else:
                people_present = prev_attr_list[j]['peoplePresent']
            prev_attr_list[j]['peoplePresent'] = people_present #Set previous value

            lanes_wzdx.append(lane)

        # road_event_id
        lanes_obj['road_event_id'] = str(uuid.uuid4())

        # feed_info_id
        #lanes_obj['feed_info_id'] = 'unknown'

        # road_name
        lanes_obj['road_name'] = 'unknown'

        # direction
        lanes_obj['direction'] = 'unknown'

        # beginning_accuracy
        lanes_obj['beginning_accuracy'] = 'estimated'

        # ending_accuracy
        lanes_obj['ending_accuracy'] = 'estimated'

        # start_date_accuracy
        lanes_obj['start_date_accuracy'] = 'estimated'

        # end_date_accuracy
        lanes_obj['end_date_accuracy'] = 'estimated'

        # total_num_lanes
        lanes_obj['total_num_lanes'] = num_lanes

        # reduced_speed_limit
        lanes_obj['reduced_speed_limit'] = reduced_speed_limit #Will either be set to the reference value or a lower value if found

        # workser_present
        lanes_obj['workers_present'] = people_present

        # vehicle_impact
        num_closed_lanes = 0
        for lane in lanes_wzdx:
            if lane['lane_status'] == 'closed':
                num_closed_lanes = num_closed_lanes + 1
        if num_closed_lanes == 0:
            lanes_obj['vehicle_impact'] = 'all_lanes_open'
        elif num_closed_lanes == num_lanes:
            lanes_obj['vehicle_impact'] = 'all_lanes_closed'
        else:
            lanes_obj['vehicle_impact'] = 'some_lanes_closed'

        # start_date
        start_date = RSM['commonContainer']['eventInfo']['startDateTime'] #Offset is in minutes from UTC (-5 hours, ET), unused
        lanes_obj['start_date'] = str(start_date['year']+'-'+form_len(start_date['month'])+'-'+form_len(start_date['day'])+'T'+form_len(start_date['hour'])+':'+form_len(start_date['minute'])+':00Z')
        
        # end_date
        end_date = RSM['commonContainer']['eventInfo']['endDateTime']
        lanes_obj['end_date'] = str(end_date['year']+'-'+form_len(end_date['month'])+'-'+form_len(end_date['day'])+'T'+form_len(end_date['hour'])+':'+form_len(end_date['minute'])+':00Z')
        
        #type_of_work
        #maintenance, minor-road-defect-repair, roadside-work, overhead-work, below-road-work, barrier-work, surface-work, painting, roadway-relocation, roadway-creation
        #Maybe use cause code??
        lanes_obj['types_of_work'] = []
        #if cause_code == 3: #No other options are available
        lanes_obj['types_of_work'].append({'type_name': 'roadside-work', 'is_architectual_change': False})

        lanes_obj['lanes'] = lanes_wzdx

        # properties
        lanes_obj_properties = {}
        lanes_obj_properties['type'] = 'Feature'
        lanes_obj_properties['properties'] = lanes_obj
        lanes_obj_properties['geometry'] = geometry

        nodes_wzdx.append(lanes_obj_properties)
    return nodes_wzdx

with open('RSZW_MAP_xml_File-20191208-110718-1_of_1.exer', 'r') as frsm:
    #rsm = rsm_creator('heh')
    #f.write(json2xml.Json2xml(rsm).to_xml())
    #rsm_xml = xmltodict.unparse(rsm, pretty=True)
    xmlSTRING = frsm.read()
    rsm_obj = xmltodict.parse(xmlSTRING)
    #with open('RSM_example.json', 'w') as frsm_json:
    #    frsm_json.write(json.dumps(rsm_obj, indent=2))
    wzdx = wzdx_creator(rsm_obj)
    with open('wzdx_test.geojson', 'w') as fwzdx:
        fwzdx.write(json.dumps(wzdx, indent=2))