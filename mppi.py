import math
import numpy as np
import matplotlib.pyplot as plt
from typing import Tuple

import requests














class MPPIControllerForPathTracking():
    def __init__(
            self,
            delta_t: float = 0.05,
            wheel_base: float = 2.5, # [m]
            max_steer_abs: float = 0.523, # [rad]
            max_accel_abs: float = 200.000, # [m/s^2]
            ref_path = np.genfromtxt('data/straight_line.csv', delimiter=',', skip_header=1),
            horizon_step_T: int = 30,
            number_of_samples_K: int = 1000,
            param_exploration: float = 0.0,
            param_lambda: float = 50.0,
            param_alpha: float = 1.0,
            sigma: np.ndarray = np.array([[0.5, 0.0], [0.0, 0.1]]), 
            stage_cost_weight: np.ndarray = np.array([50.0, 50.0, 1.0, 20.0]), # weight for [x, y, yaw, v]
            terminal_cost_weight: np.ndarray = np.array([50.0, 50.0, 1.0, 20.0]), # weight for [x, y, yaw, v]
            visualize_optimal_traj = True,  # if True, optimal trajectory is visualized
            visualze_sampled_trajs = False, # if True, sampled trajectories are visualized
    ) -> None:
        """initialize mppi controller for path-tracking"""
        # mppi parameters
        self.dim_x = 4 # dimension of system state vector
        self.dim_u = 2 # dimension of control input vector
        self.T = horizon_step_T # prediction horizon
        self.K = number_of_samples_K # number of sample trajectories
        self.param_exploration = param_exploration  # constant parameter of mppi
        self.param_lambda = param_lambda  # constant parameter of mppi
        self.param_alpha = param_alpha # constant parameter of mppi
        self.param_gamma = self.param_lambda * (1.0 - (self.param_alpha))  # constant parameter of mppi
        self.Sigma = sigma # deviation of noise
        self.stage_cost_weight = stage_cost_weight
        self.terminal_cost_weight = terminal_cost_weight
        self.visualize_optimal_traj = visualize_optimal_traj
        self.visualze_sampled_trajs = visualze_sampled_trajs

        # vehicle parameters
        self.delta_t = delta_t #[s]
        self.wheel_base = wheel_base#[m]
        self.max_steer_abs = max_steer_abs # [rad]
        self.max_accel_abs = max_accel_abs # [m/s^2]
        self.ref_path = ref_path

        # mppi variables
        self.u_prev = np.zeros((self.T, self.dim_u))

        # ref_path info
        self.prev_waypoints_idx = 0


    def hello(self):
        print("hello world")
        return "Hello world"

    def calc_control_input(self, observed_x: np.ndarray) -> Tuple[float, np.ndarray]:
        """calculate optimal control input"""
        # load privious control input sequence
        u = self.u_prev
        # print("INPUT SEQUENCE U")
        # print(u)

        print(f"observed x = {observed_x}")
        print(f"type -> {type(observed_x)}")

        # set initial x value from observation
        x0 = observed_x

        print("made it to line 87 in calc_control")
        # get the waypoint closest to current vehicle position 
        self._get_nearest_waypoint(x0[0], x0[1], update_prev_idx=True)
        print("finished waypoints")
        if self.prev_waypoints_idx >= self.ref_path.shape[0]-1:
            print("[ERROR] Reached the end of the reference path.")
            raise IndexError

        print("right before S")
        # prepare buffer
        S = np.zeros((self.K)) # state cost list
        print("s ran")
        # sample noise
        epsilon = self._calc_epsilon(self.Sigma, self.K, self.T, self.dim_u) # size is self.K x self.T

        # prepare buffer of sampled control input sequence
        v = np.zeros((self.K, self.T, self.dim_u)) # control input sequence with noise

        # loop for 0 ~ K-1 samples
        for k in range(self.K):         

            # set initial(t=0) state x i.e. observed state of the vehicle
            x = x0

            # loop for time step t = 1 ~ T
            for t in range(1, self.T+1):

                # get control input with noise
                if k < (1.0-self.param_exploration)*self.K:
                    v[k, t-1] = u[t-1] + epsilon[k, t-1] # sampling for exploitation
                else:
                    v[k, t-1] = epsilon[k, t-1] # sampling for exploration

                # update x
                x = self._F(x, self._g(v[k, t-1]))

                # add stage cost
                S[k] += self._c(x) + self.param_gamma * u[t-1].T @ np.linalg.inv(self.Sigma) @ v[k, t-1]

            # add terminal cost
            S[k] += self._phi(x)

        # compute information theoretic weights for each sample
        w = self._compute_weights(S)

        # calculate w_k * epsilon_k
        w_epsilon = np.zeros((self.T, self.dim_u))
        for t in range(0, self.T): # loop for time step t = 0 ~ T-1
            for k in range(self.K):
                w_epsilon[t] += w[k] * epsilon[k, t]

        # apply moving average filter for smoothing input sequence
        w_epsilon = self._moving_average_filter(xx=w_epsilon, window_size=10)

        # update control input sequence
        u += w_epsilon
        print("u += w_epsiolon finished")
        # calculate optimal trajectory
        optimal_traj = np.zeros((self.T, self.dim_x))
        if self.visualize_optimal_traj:
            x = x0
            for t in range(0, self.T): # loop for time step t = 0 ~ T-1
                x = self._F(x, self._g(u[t]))
                optimal_traj[t] = x

        # calculate sampled trajectories
        sampled_traj_list = np.zeros((self.K, self.T, self.dim_x))
        sorted_idx = np.argsort(S) # sort samples by state cost, 0th is the best sample
        if self.visualze_sampled_trajs:
            for k in sorted_idx:
                x = x0
                for t in range(0, self.T): # loop for time step t = 0 ~ T-1
                    x = self._F(x, self._g(v[k, t]))
                    sampled_traj_list[k, t] = x

        # update privious control input sequence (shift 1 step to the left)
        self.u_prev[:-1] = u[1:]
        self.u_prev[-1] = u[-1]
        # print(self.u[0])

        # return optimal control input and input sequence
        # PRINT THIS OUT!!! U -> CONTROL SIGNAL
        # print(f"Optimal Traj = {optimal_traj}")
        # print(f"INPUT SEQUENCE = {self.u[0]}")

        return u[0], u, optimal_traj, sampled_traj_list

    def _calc_epsilon(self, sigma: np.ndarray, size_sample: int, size_time_step: int, size_dim_u: int) -> np.ndarray:
        """sample epsilon"""
        # check if sigma row size == sigma col size == size_dim_u and size_dim_u > 0
        if sigma.shape[0] != sigma.shape[1] or sigma.shape[0] != size_dim_u or size_dim_u < 1:
            print("[ERROR] sigma must be a square matrix with the size of size_dim_u.")
            raise ValueError

        # sample epsilon
        mu = np.zeros((size_dim_u)) # set average as a zero vector
        epsilon = np.random.multivariate_normal(mu, sigma, (size_sample, size_time_step))
        return epsilon

    def _g(self, v: np.ndarray) -> float:
        """clamp input"""
        # limit control inputs
        v[0] = np.clip(v[0], -self.max_steer_abs, self.max_steer_abs) # limit steering input
        v[1] = np.clip(v[1], -self.max_accel_abs, self.max_accel_abs) # limit acceleraiton input
        return v

    def _c(self, x_t: np.ndarray) -> float:
        """calculate stage cost"""
        # parse x_t
        x, y, yaw, v = x_t
        yaw = ((yaw + 2.0*np.pi) % (2.0*np.pi)) # normalize theta to [0, 2*pi]

        # calculate stage cost
        _, ref_x, ref_y, ref_yaw, ref_v = self._get_nearest_waypoint(x, y)
        stage_cost = self.stage_cost_weight[0]*(x-ref_x)**2 + self.stage_cost_weight[1]*(y-ref_y)**2 + \
                     self.stage_cost_weight[2]*(yaw-ref_yaw)**2 + self.stage_cost_weight[3]*(v-ref_v)**2
        return stage_cost

    def _phi(self, x_T: np.ndarray) -> float:
        """calculate terminal cost"""
        # parse x_T
        x, y, yaw, v = x_T
        yaw = ((yaw + 2.0*np.pi) % (2.0*np.pi)) # normalize theta to [0, 2*pi]

        # calculate terminal cost
        _, ref_x, ref_y, ref_yaw, ref_v = self._get_nearest_waypoint(x, y)
        terminal_cost = self.terminal_cost_weight[0]*(x-ref_x)**2 + self.terminal_cost_weight[1]*(y-ref_y)**2 + \
                        self.terminal_cost_weight[2]*(yaw-ref_yaw)**2 + self.terminal_cost_weight[3]*(v-ref_v)**2
        return terminal_cost

    def _get_nearest_waypoint(self, x: float, y: float, update_prev_idx: bool = False):
        """search the closest waypoint to the vehicle on the reference path"""

        SEARCH_IDX_LEN = 25 # [points] forward search range
        prev_idx = self.prev_waypoints_idx
        dx = [x - ref_x for ref_x in self.ref_path[prev_idx:(prev_idx + SEARCH_IDX_LEN), 0]]
        dy = [y - ref_y for ref_y in self.ref_path[prev_idx:(prev_idx + SEARCH_IDX_LEN), 1]]
        d = [idx ** 2 + idy ** 2 for (idx, idy) in zip(dx, dy)]
        min_d = min(d)
        nearest_idx = d.index(min_d) + prev_idx

        # get reference values of the nearest waypoint
        ref_x = self.ref_path[nearest_idx,0]
        ref_y = self.ref_path[nearest_idx,1]
        ref_yaw = self.ref_path[nearest_idx,2]
        ref_v = self.ref_path[nearest_idx,3]

        # print(f"nearest waypoint markers: \n ")
        # print(f"refx = {ref_x}")
        # print(f"refy = {ref_y}")
        # print(f"refyaw = {ref_yaw}")
        # print(f"refv = {ref_v}")
        # print(f"? nearest idx = {nearest_idx}?")

        # update nearest waypoint index if necessary
        if update_prev_idx:
            self.prev_waypoints_idx = nearest_idx 

        return nearest_idx, ref_x, ref_y, ref_yaw, ref_v

    def _F(self, x_t: np.ndarray, v_t: np.ndarray) -> np.ndarray:
        """calculate next state of the vehicle"""
        # get previous state variables
        x, y, yaw, v = x_t
        steer, accel = v_t

        # prepare params
        l = self.wheel_base
        dt = self.delta_t

        # update state variables
        new_x = x + v * np.cos(yaw) * dt
        new_y = y + v * np.sin(yaw) * dt
        new_yaw = yaw + v / l * np.tan(steer) * dt
        new_v = v + accel * dt

        # return updated state
        x_t_plus_1 = np.array([new_x, new_y, new_yaw, new_v])
        return x_t_plus_1

    def _compute_weights(self, S: np.ndarray) -> np.ndarray:
        """compute weights for each sample"""
        # prepare buffer
        w = np.zeros((self.K))

        # calculate rho
        rho = S.min()

        # calculate eta
        eta = 0.0
        for k in range(self.K):
            eta += np.exp( (-1.0/self.param_lambda) * (S[k]-rho) )

        # calculate weight
        for k in range(self.K):
            w[k] = (1.0 / eta) * np.exp( (-1.0/self.param_lambda) * (S[k]-rho) )
        return w

    def _moving_average_filter(self, xx: np.ndarray, window_size: int) -> np.ndarray:
        """apply moving average filter for smoothing input sequence
        Ref. https://zenn.dev/bluepost/articles/1b7b580ab54e95
        Note: The original MPPI paper uses the Savitzky-Golay Filter for smoothing control inputs.
        """
        b = np.ones(window_size)/window_size
        dim = xx.shape[1]
        xx_mean = np.zeros(xx.shape)

        for d in range(dim):
            xx_mean[:,d] = np.convolve(xx[:,d], b, mode="same")
            n_conv = math.ceil(window_size/2)
            xx_mean[0,d] *= window_size/n_conv
            for i in range(1, n_conv):
                xx_mean[i,d] *= window_size/(i+n_conv)
                xx_mean[-i,d] *= window_size/(i + n_conv - (window_size % 2)) 
        return xx_mean
    

# if __name__ == '__main__':
#     # simulation settings
#     delta_t = 0.05 # [sec]
#     sim_steps = 50 # [steps]
#     print(f"[INFO] delta_t : {delta_t:.2f}[s] , sim_steps : {sim_steps}[steps], total_sim_time : {delta_t*sim_steps:.2f}[s]")

#     # load and visualize reference path
#     ref_path = np.genfromtxt('/data/telemetry.csv', delimiter=',', skip_header=1)
#     plt.title("Reference Path")
#     plt.plot(ref_path[:,0], ref_path[:,1])
#     plt.show()

#     # initialize a vehicle as a control target
#     vehicle = Vehicle(
#         wheel_base=2.5,
#         max_steer_abs=0.523, # [rad]
#         max_accel_abs=200.000, # [m/s^2]
#         ref_path = ref_path[:, 0:2], # ndarray, size is <num_of_waypoints x 2>
#     )

#     vehicle.reset(
#         init_state = np.array([0.0, 1.0, 0.0, 0.0]), # [x[m], y[m], yaw[rad], v[m/s]]
#     )

#     # initialize a mppi controller for the vehicle
#     mppi = MPPIControllerForPathTracking(
#         delta_t = delta_t*2.0, # [s]
#         wheel_base = 2.5, # [m]
#         max_steer_abs = 0.523, # [rad]
#         max_accel_abs = 200.000, # [m/s^2]
#         ref_path = ref_path, # ndarray, size is <num_of_waypoints x 2>
#         horizon_step_T = 20, # [steps]
#         # 5 stepm 20 samples
#         number_of_samples_K = 500, # [samples]
#         param_exploration = 0.0,
#         param_lambda = 100.0,
#         param_alpha = 0.98,
#         sigma = np.array([[0.075, 0.0], [0.0, 2.0]]),
#         stage_cost_weight = np.array([50.0, 50.0, 1.0, 20.0]), # weight for [x, y, yaw, v]
#         terminal_cost_weight = np.array([50.0, 50.0, 1.0, 20.0]), # weight for [x, y, yaw, v]
#         visualze_sampled_trajs = True
#     )


#     # print(f"current state = {current_state}")

#     # simulation loop WILL NOT BE IN SERVER/SCRIPT
#     # for i in range(sim_steps):

#     #     # get current state of vehicle
#     #     # LUA POST
#     #     current_state = vehicle.get_state()
#     #     print(f"current vehicle state = {vehicle.get_state()}")
#     #     # THIS WILL BE REPLACED BY A GET STATE

#         # RUN WHEN LUA GET REQUEST 
#     try:
#         # calculate input force with MPPI
#                                                                                 # import into server file
#         optimal_input, optimal_input_sequence, optimal_traj, sampled_traj_list = mppi.calc_control_input(
#             observed_x = current_state
#         )
#     except IndexError as e:
#         # the vehicle has reached the end of the reference path
#         print("[ERROR] IndexError detected. Terminate simulation.")
        

#     # show animationvehicle.show_animation(interval_ms=int(delta_t))
#     print(delta_t)
#     # vehicle.show_animation(interval_ms=(delta_t))
#     # save animation
#     # vehicle.save_animation("mppi_pathtracking_demo.mp4", interval=int(delta_t * 1000), movie_writer="ffmpeg") # ffmpeg is required to write mp4 file