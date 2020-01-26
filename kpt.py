import urllib, json
import urllib.request
import os.path
import time
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

cred = credentials.Certificate('onlinekyivpastrans-firebase-adminsdk-n6s6j-294c3b7eb1.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://onlinekyivpastrans.firebaseio.com/'
})
ref = db.reference('vehicles')
base = ref.get()
if base is None:
    base = {}

routes = {}
nearRadius = 0.001
bigRadius = 0.005
route_list_url = "https://online.kpt.kyiv.ua/api/route/list"
location_list_url = "https://online.kpt.kyiv.ua/socket.io/?EIO=3&transport=polling"


def current_milli_time():
    return int(round(time.time() * 1000))


def typeToText(type):
    if type == 1:
        return "tram"
    elif type == 2:
        return "trolleybus"
    elif type == 3:
        return "bus"
    elif type == 4:
        return "train"
    elif type == 9:
        return "route-taxi"
    elif type == 20:
        return "metro"
    else:
        return "undefined"


def init():
    with urllib.request.urlopen(route_list_url) as response:
        data = json.loads(response.read())
        for route in data:
            print(f'Route for {route["id"]} ...')
            response2 = urllib.request.urlopen(f'https://online.kpt.kyiv.ua/api/route/view?id={route["id"]}')
            route_data = json.loads(response2.read())
            stops = []
            for stop in route_data["stops"]:
                stops.append({"name": stop["stop"]["name"], "lat": float(stop["stop"]["lat"]), "lng": float(stop["stop"]["lng"]), "pos": stop["pos"]})
            routes[route["id"]] = {"number": route["number"], "type": route["type"], "stops": stops, "vehicles": {}}
            #print(f'{route["number"]} - {typeToText(route["type"])} - {route["id"]}')


def isNear(lat1, lng1, lat2, lng2):
    return (lat1 - lat2) ** 2 + (lng1 - lng2) ** 2 < nearRadius ** 2


def isFar(lat1, lng1, lat2, lng2):
    return (lat1 - lat2) ** 2 + (lng1 - lng2) ** 2 > bigRadius ** 2


def check(vehicles):
    updates = {}
    for vehicle in vehicles:
        route_id = vehicle["route_id"]
        vehicle_id = vehicle["vehicle_id"]
        if str(route_id) not in routes:
            continue
        route = routes[str(route_id)]
        for stop in route["stops"]:
            if isNear(stop["lat"], stop["lng"], vehicle["lat"], vehicle["lng"]):
                if vehicle_id not in route["vehicles"] or (route["vehicles"][vehicle_id]["stop_name"] != stop["name"] and isFar(route["vehicles"][vehicle_id]["lat"], route["vehicles"][vehicle_id]["lng"], vehicle["lat"], vehicle["lng"])):
                    route["vehicles"][vehicle_id] = {"stop_name": stop["name"], "lat": vehicle["lat"], "lng": vehicle["lng"], "time": current_milli_time()}
                    current_time = current_milli_time()
                    if vehicle_id not in base:
                        updates[f'{vehicle_id}/route_number'] = route["number"]
                        updates[f'{vehicle_id}/route_type'] = route["type"]
                        base[vehicle_id] = '+'
                    updates[f'{vehicle_id}/locations/{current_time}'] = stop["name"]
                    print(f'({vehicle_id})Arrived: ({typeToText(route["type"])}) {route["number"]} at {stop["name"]}')
    if len(updates) > 0:
        ref.update(updates)
    print("-" * 50)


def cutJSON(str, begin_char, close_char):
    first_bracket = str.find(begin_char)
    second_bracket = str.rfind(close_char)
    if second_bracket == -1:
        second_bracket = len(str) - 1
    if first_bracket == -1:
        first_bracket = 0
    return str[first_bracket:second_bracket + 1]


if os.path.exists("data.txt"):
    print("Data already exists. Reading ...")
    f = open("data.txt", "r") 
    routes = json.loads(f.read())["routes"]
else:
    print("Getting data ...")
    init()
    dictionary = {"routes": routes}
    f = open("data.txt", "w")
    f.write(json.dumps(dictionary))

print("Init finished")
while True:
    response = cutJSON(str(urllib.request.urlopen(location_list_url).read()), '{', '}')
    sid = json.loads(response)["sid"]
    response = cutJSON(str(urllib.request.urlopen(location_list_url + "&sid=" + sid).read()), '[', ']')
    data = json.loads(response)[1]
    vehicles = []
    for item in data:
        transport = item.split(',')
        vehicles.append({"vehicle_id": transport[0], "route_id" : transport[1], "lat" : float(transport[2]), "lng" : float(transport[3])})
    check(vehicles)
    time.sleep(10)