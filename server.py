from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import time
import re
import mppi
import numpy as np

mppi_controller = mppi.MPPIControllerForPathTracking()
# keeps track of most recent input sequence update
global_control_sequence = None
# set depending on sampling rate (currently every 15 out of 60 frames)
delta_t = 0.25
wheel_base = 1.0
# updated globally
x = None
y = None
yaw = None
velocity = None
steering = None
acceleration = None

# TODO
# get correct optimal line CHECK
# Pass values into MPPI script
# Call mppi, pause/yield bizhawk
# return and convert mppi output value into directional input for bizhawk cloent

class BizHawkHandler(BaseHTTPRequestHandler):
    # Store the current action
    current_action = ""
    # Store the latest position data
    latest_position = None
    # Store timestamp of last position update
    last_update_time = 0
    
    def _set_headers(self, content_type='text/html'):
        self.send_response(200)
        self.send_header('Content-type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')  # For CORS
        self.end_headers()
   
    def do_GET(self):
        print(f"GET request to {self.path}")
        # print(f"self is {self}")
        self.path = "/bizhawk/control"
        if self.path == '/bizhawk':
            self._set_headers()
            response = "BizHawk HTTP Server is running!"
            self.wfile.write(response.encode('utf-8'))
        elif self.path == '/bizhawk/control':
            # Return the current action without removing it

            print(f"global control was updated to {global_control_sequence} last step")
            print(f"steer output = {steering}")
            '''
            positve radian is left
            negative radian is right
            zero radian is neutral
            radians * 57.2958 = degrees!
            just make positive = left, negative = right
            '''
            print(f"accel output = {acceleration}")

            self._set_headers()
            # THIS RESPONDS TO CLIENT'S GET
            response = "Steering: " + str(steering) + ", Acceleration: " + str(acceleration)
            self.wfile.write(str(response).encode('utf-8'))
            print(".\n.\n.")
        else:
            self._set_headers()
            print("broken shit, why peek?")
            response = f"Path {self.path} not found. Try /bizhawk instead."
            self.wfile.write(response.encode('utf-8'))
    
    def do_POST(self):
        print(f"POST request to {self.path}")
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        # print("DO POST RECEIVED")
        current = post_data.decode('utf-8')
        print("Got raw string:", current)

        
        if self.path == '/bizhawk':
            try:
                data = json.loads(post_data.decode('utf-8'))
                
                # ACTION CODE
                # Check if the data contains an action command
                if 'action' in data:
                    BizHawkHandler.current_action = data['action']

                    print(f"Set current action to: {BizHawkHandler.current_action}")
                
                self._set_headers('application/json')
                response = {"status": "success", "message": "Data received successfully"}
                self.wfile.write(json.dumps(response).encode('utf-8'))
            except json.JSONDecodeError:
                self._set_headers('application/json')
                response = {"status": "error", "message": "Invalid JSON data"}
                self.wfile.write(json.dumps(response).encode('utf-8'))


        # THIS IS WHERE WE HANDLE POSITION UPDATES
        # Handle position updates
        elif self.path == '/bizhawk/position':
            try:
                position_data = post_data.decode('utf-8')
    
                # print("YOOOOOO LINE 93, position data = ")
                print(position_data)
                # print(f"position_data ", {position_data})
                # values = re.findall(r'%3A([^\s+]+)', position_data)
                values = re.findall(r'%3A([^+]+)', position_data)
                # print(f"VALUES = {values}")
                # print(f"x = {values[0]}")
                # print(f"y = {values[1]}")
                # print(f"yaw = {values[2]}")
                # print(f"velocity = {values[3]}")
                # print(f"steering = {values[4]}")
                # print(f"acceleration = {values[5]}")
                x = values[0]
                y = values[1]
                yaw = values[2]
                velocity = values[3]

                print("values done")
                '''
                            yaw grid

                             12,288
                                ^
             0, 49,152  <                >   24,576
                                v
                            36,864
                '''
                # current state = [x, y, yaw, vel]
                # current_state = [x, y, yaw, velocity]
                current_state = np.array([x, y, velocity, yaw], dtype=float)
                print(f"current state = {current_state}")

                
                # import into server file
                optimal_input = mppi_controller.calc_control_input(current_state)
                # print(f"current state = {int(current_state)}")

                # update directional input after calc_control
                global global_control_sequence 
                global_control_sequence = optimal_input[0]
                global steering
                global acceleration
                steering = global_control_sequence[0]
                acceleration = global_control_sequence[1]
                print(f"optimal input sequence (steer, accel) = {optimal_input[0]}")
                # print("bruhs worked")
                self._set_headers()
                self.wfile.write("Position updated".encode('utf-8'))

            except Exception as e:
                print(f"Error processing position update: {e}")
                self._set_headers()
                self.wfile.write(f"Error: {str(e)}".encode('utf-8'))
        else:
            self._set_headers('application/json')
            print("hi broken post")
            response = {"status": "error", "message": f"Path {self.path} not found"}
            self.wfile.write(json.dumps(response).encode('utf-8'))

def run_server(host="127.0.0.1", port=8088):
    server_address = (host, port)
    httpd = HTTPServer(server_address, BizHawkHandler)
    print(f"Starting server at http://{host}:{port}/bizhawk")
    httpd.serve_forever()

if __name__ == '__main__':
    run_server()