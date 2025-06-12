import mppi

mppi_controller = mppi.MPPIControllerForPathTracking()

mppi_controller.hello()
current_state = [0, 0, 0, 0]
mppi_controller.calc_control_input(current_state)