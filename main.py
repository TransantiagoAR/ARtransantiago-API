from flask import request, url_for
from flask_api import FlaskAPI, status, exceptions
import requests
import googlemaps
import aiohttp
import asyncio
import selectors

app = FlaskAPI(__name__)


TRANSANTIAGO_URL = 'http://www.transantiago.cl/restservice/rest'
PREDICTOR_URL = 'http://www.transantiago.cl/predictor'
SERVICIOS_URL = '{0}/getservicios/all'.format(TRANSANTIAGO_URL)
PUNTO_PARADA_URL = '{0}/getpuntoparada'.format(TRANSANTIAGO_URL) # PARAMS: lat, lon, bip
PREDICCION_URL = '{0}/prediccion'.format(PREDICTOR_URL) #PARAMS: codsimtm codser
RECORRIDO_URL = '{0}/getrecorrido'.format(TRANSANTIAGO_URL) 

gmaps = googlemaps.Client( key='AIzaSyDOAu0c-3OMkpLeqi0tdJ9Jrr-2XygDmgY')


@app.route("/stop", methods=['GET'])
def stop(): 
    if request.method != 'GET':
        return '', status.HTTP_400_BAD_REQUEST

    #print(type(request.args))
    if request.args.get('pid') is None:
        return '', status.HTTP_400_BAD_REQUEST
    
    pid = request.args.get('pid')

    r = requests.get(PREDICCION_URL, params=(('codsimt', pid),('codser', ''))).json()
    
    services = []
    for s in r['servicios']["item"]:
        if s["horaprediccionbus1"]:
            services.append({"cod": s["servicio"], "eta": s["horaprediccionbus1"]})
        if s["horaprediccionbus2"]:
            services.append({"cod": s["servicio"], "eta": s["horaprediccionbus2"]})


    return { "pid" :  r['paradero'], "services": services }


# @app.route("/stop/<int:key>/", methods=['GET'])
# def stop_info(key): 
#     if request.method != 'GET':
#         return status.HTTP_400_BAD_REQUEST
#     return status.HTTP_204_NO_CONTENT

def areEqualCoor(c1, c2):
    return c1[0] == c2[0] and c1[1] == c2[1]

def as_tuple(list):
    return (list[0], list[1])

def line(step):
    start = step['start_location']
    end = step['end_location']
    return [ [start['lat'], start['lng']], [end['lat'], end['lng']] ]

def get_directions(stop1, stop2):

    rides_directions = gmaps.directions(origin = as_tuple(stop1), destination = as_tuple(stop2), mode='driving')
    # print(as_tuple(stop1), as_tuple(stop2))
    steps = []
    queue = [rides_directions[0]['legs'][0]]
    while len(queue) > 0:
        actual = queue.pop()
        steps.append( line(actual) )
        if 'steps' in actual.keys():
            steps.pop()
            for i in range(len(actual['steps'])-1, -1 , -1):
                queue.append(actual['steps'][i])
    return steps

def rev(list_coord):
    list_coord.reverse()
    for l in list_coord:
        l.reverse()
    return list_coord

def directions(journey):
    return get_directions(journey[0], journey[1]) + get_directions(journey[1], journey[2]) 

def etass(etas):
    et = []
    for e in etas['servicios']['item']:
        if e["horaprediccionbus1"]:
            et.append(e["horaprediccionbus1"])
        if e["horaprediccionbus2"]:
            et.append(e["horaprediccionbus2"])
        if len(et) == 0:
            et.append("No hay buses que se dirijan al paradero.")
    return et

def stopss(journey, stops):
    st = []
    for i in range(len(stops)):
        st.append({'stop': stops[i], 'pos': journey[i]})
    return st

def ride_repr(ride, journey, etas, stops):
    return { 'pid': ride['cod'], 'journeys': directions(journey), 'etas': etass(etas), 'stops': stopss(journey, stops)}

@asyncio.coroutine
def get_recorrido(x):
    data = yield from aiohttp.request('GET', '{0}/{1}'.format(RECORRIDO_URL, x['cod']))
    return (yield from data.json())

def all_recorridos(rides):
    rides_json_requests = []
    for ride in rides:
        rides_json_requests.append(asyncio.Task(get_recorrido(ride)))

    return rides_json_requests

@asyncio.coroutine
def get_etas(x, nearest):
    data = yield from aiohttp.request('GET', PREDICCION_URL, params=(('codsimt', nearest),('codser', x['cod'])) )
    return (yield from data.json())

def all_etas(rides, nearest):
    rides_json_requests = []
    for ride in rides:
        rides_json_requests.append(asyncio.Task(get_etas(ride, nearest)))

    return rides_json_requests

@app.route("/journey", methods=['GET'])
def journey_look_up():
    if request.method != 'GET':
        return '', status.HTTP_400_BAD_REQUEST

    ### GET NEAREST STOP 
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    if lat is None or lon is None:
        return '', status.HTTP_400_BAD_REQUEST

    r = requests.get(PUNTO_PARADA_URL, params=(('lat', lat), ('lon', lon), ('bip', '1')))
    # for p in r.json():
    #     print(p['distancia'])

    if len(r.json()) == 0:
        return []
    nearest_stop = r.json()[0] #assuming first is nearest
    # for s in nearest_stop['servicios']:
    #     print(s['cod'])
    
    rides = nearest_stop['servicios']
    # rides_jsons = list(all_recorridos(rides))

    selector = selectors.SelectSelector()
    loop = asyncio.SelectorEventLoop(selector)
    asyncio.set_event_loop(loop)

    loop = asyncio.get_event_loop()
    # loop = asyncio.ProactorEventLoop()
    # asyncio.set_event_loop(loop)
    rides_jsons = loop.run_until_complete(asyncio.gather(*all_recorridos(rides)))

    # print(rides_jsons)
    for i in range(len(rides_jsons)):
        # print(rides[i]['destino'], rides_jsons[i][0]['destino'], rides_jsons[i][1]['destino'])
        # print(len(rides_jsons[i]), 0 if  rides_jsons[i][0]['destino'] in rides[i]['destino'] else 1)
        rides_jsons[i] = rides_jsons[i][0] if  rides_jsons[i][0]['destino'] in rides[i]['destino'] else rides_jsons[i][1]
    
    ### GET RIDES STOPS

    rides_stops = list(map(lambda x:  list(map( lambda y: y['pos']  , x['paradas'] ))  ,  rides_jsons))
    rides_stops_cod = list(map(lambda x:  list(map( lambda y: y['cod']  , x['paradas'] ))  ,  rides_jsons))
    
    #print(nearest_stop['pos'])
    for i in range(len(rides_jsons)):
        # print(rides_jsons[i]['cod'])
        index = -1
        for j in range(len(rides_stops[i])):
            # print(rides_stops[i][j])
            if areEqualCoor(rides_stops[i][j], nearest_stop['pos']):
                index =  j
        # print(index)
        # print(rides_stops[i])
        low_index = index - 2 if index > 2 else 0
        top_index = index + 3 if len(rides_stops[i]) - index >= 3 else index
        rides_stops[i] = rides_stops[i][low_index:top_index] if index > -1 else None
        rides_stops_cod[i] = rides_stops_cod[i][low_index:top_index] if index > -1 else None
        # print(rides_stops[i])s
    
    etas_jsons = loop.run_until_complete(asyncio.gather(*all_etas(rides, nearest_stop['cod'])))

    response = []

    for i in range(len(rides_jsons)):
        if not rides_stops[i] is None:
            response.append(ride_repr(rides_jsons[i], rides_stops[i], etas_jsons[i], rides_stops_cod[i]))

    return response


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
