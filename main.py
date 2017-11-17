from flask import request, url_for
from flask_api import FlaskAPI, status, exceptions
import requests
import googlemaps

app = FlaskAPI(__name__)


TRANSANTIAGO_URL = 'http://www.transantiago.cl/restservice/rest'
SERVICIOS_URL = '{0}/getservicios/all'.format(TRANSANTIAGO_URL)
PUNTO_PARADA_URL = '{0}/getpuntoparada'.format(TRANSANTIAGO_URL) # PARAMS: lat, lon, bip
PREDICCION_URL = '{0}/prediccion'.format(TRANSANTIAGO_URL) #PARAMS: codsimtm codser
RECORRIDO_URL = '{0}/getrecorrido'.format(TRANSANTIAGO_URL) #PARAMS: codsimtm codser


gmaps = googlemaps.Client( key='AIzaSyDOAu0c-3OMkpLeqi0tdJ9Jrr-2XygDmgY	')


stops = [1 ,2, 3]

def stop_repr(stop):
    return {
        'id': 1
    }


@app.route("/stop/", methods=['GET'])
def stop(): 
    if request.method != 'GET':
        return '', status.HTTP_400_BAD_REQUEST

    #print(type(request.args))
    if request.args.get('pid') is None:
        return '', status.HTTP_400_BAD_REQUEST

    r = requests.get(SERVICIOS_URL)

    if not request.args.get('pid') in r.json():
        return '', status.HTTP_404_NOT_FOUND

    return { "PID" : request.args.get('pid') }


# @app.route("/stop/<int:key>/", methods=['GET'])
# def stop_info(key): 
#     if request.method != 'GET':
#         return status.HTTP_400_BAD_REQUEST
#     return status.HTTP_204_NO_CONTENT


@app.route("/journey/", methods=['GET'])
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

    nearest_stop = r.json()[0] #assuming first is nearest
    # for s in nearest_stop['servicios']:
    #     print(s['cod'])
    
    rides = nearest_stop['servicios']
    rides_jsons = list(map( lambda x : requests.get('{0}/{1}'.format(RECORRIDO_URL, x['cod']) ).json(), rides))
    for i in range(len(rides_jsons)):
        print(rides[i]['destino'], rides_jsons[i][0]['destino'], rides_jsons[i][1]['destino'])
        rides_jsons[i] = rides_jsons[i][0] if  rides_jsons[i][0]['destino'] in rides[i]['destino'] else rides_jsons[i][1]
    
    ### GET RIDES STOPS

    rides_stops = list(map(lambda x:  list(map( lambda y: y['pos']  , x['paradas'] ))  ,  rides_jsons))

    def areEqualCoor(c1, c2):
        return c1[0] == c2[0] and c1[1] == c2[1]

    for i in range(len(rides_jsons)):
        print(rides_jsons[i]['cod'])
        index = -1
        for j in range(len(rides_stops[i])):
            # print(rides_stops[i][j])
            if areEqualCoor(rides_stops[i][j], nearest_stop['pos']):
                index =  j
        print(index)
        rides_stops[i] = rides_stops[i][index-1:index+2]
        print(rides_stops[i])
    

    ### GET DIRECTIONS 


    return '', status.HTTP_204_NO_CONTENT


if __name__ == "__main__":
    app.run(debug=True)

