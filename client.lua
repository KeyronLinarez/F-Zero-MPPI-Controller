print("Begin Program")
local url = "http://127.0.0.1:8088/bizhawk"
local getUrl = url .. "/control"
local postUrl = url .. "/position"  -- Changed to a new endpoint for position data
print("post url worked")
local frameCount = 0
local update
local buttons = joypad.get(1)  -- Get current button states
local B_button = false
local Left_button = false
local Right_button = false

if controller_state == nil then
    controller_state = {

        Left = false,
        Right = false,
        B = false

    }
end

-- actions performed following server requests
function request()

    local buttons = joypad.get(1)  -- Get current button states
    -- Post current state (x, y, yaw, velocity)
    -- Always read and send the position data
    local xpos = mainmemory.read_s16_le(0x000B70)
    local ypos = mainmemory.read_s16_le(0x000B90)
    local yaw = mainmemory.read_u16_le(0x000BD0)

	local xvel = mainmemory.read_s16_le(0x000B30) * 11
    local yvel = mainmemory.read_s16_le(0x000B50) * 11
    -- assuming, naively, that the combination is correct
    local velocity = math.sqrt(xvel^2 + yvel^2)
    
    local acceleration = 0
    local steering = 0

    --- ACCELERATION - Assume accleration based on player input B
    -- Slow down half as fast as accelerate
    -- CHANGE TO MAX ACCLERATION OF MPPI - 
    if buttons.B then
        acceleration = 11.11
    else
        if velocity > 0 then
            acceleration = -11.11
        else
            acceleration = 0
        end
    end

    -- CONVERT YAW TO RADIANS
	local totalUnits = 49152
    local unitsNorth = 12288  -- game angle value when pointing north
    local normalized = (unitsNorth - yaw) % totalUnits
    local degrees = (normalized / totalUnits) * 360
    local radians = degrees * (0.0174533)
    gui.drawText(80, 10, "Angle: " .. degrees)
	gui.drawText(80, 25, "Rads: " .. radians)

    local current_state = ("X-Pos:" .. tostring(xpos) .. " Y-Pos:" .. tostring(ypos) .. " Yaw:" .. tostring(radians) .. " Velocity:" .. tostring(velocity) .. " Steering:" .. tostring(steering) .. " Acceleration:" .. acceleration)
    -- CONVERT YAW TO RADIANS
    comm.httpPost(postUrl, tostring(current_state))
    update = comm.httpGet(getUrl)
end

while true do
    -- Poll every 60 frames (i.e. every 0.25 seconds) -- CHANGE TO MATCH THE SAMPLING IN MPPI (?)S
    if (math.fmod(frameCount, 10) == 0) then
        -- this does all the math
        request()
        -- print(steer_pattern)
        -- code to extraFct steering and accel values
        local steer_pattern = "%p?%d%p%d%d"
        local match_steer = string.find(update, steer_pattern)
        local steer_client = tonumber(string.sub(update, match_steer, match_steer + 4))
        print("steering = " .. steer_client)
    
        local accel_pattern = "Acceleration:%s*(%-?%d+%.%d%d)"
        local a, b, accel_client = string.find(update, accel_pattern)
        print("acceleration = " .. accel_client)
        
        -- -- STEER CODE
    local steer = tonumber(steer_client)

    if steer == nil then
        print("Invalid steering input")
        controller_state.Left = false
        controller_state.Right = false
    else
        if steer >= 0.4 then
            print("TURNING LEFT")
            controller_state.Left = true
            controller_state.Right = false
        elseif steer <= -0.4 then
            print("TURNING RIGHT")
            controller_state.Left = false
            controller_state.Right = true
        else
            -- In the center zone, no turning
            controller_state.Left = false
            controller_state.Right = false
        end
    end


        -- ACCELERATE CODE
        if tonumber(accel_client) >= -1.50 then
            print("PRESSING B")
            controller_state.B = true
        else
            controller_state.B = false
        end

    end
    -- grab acceleration
    -- print(update)


    joypad.set(controller_state, 1)

    frameCount = frameCount + 1
    emu.frameadvance() 
end

