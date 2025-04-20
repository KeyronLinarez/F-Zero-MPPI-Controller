print("Begin Program")
local url = "http://127.0.0.1:8088/bizhawk"
local getUrl = url .. "/control"
local postUrl = url .. "/position"  -- Changed to a new endpoint for position data
print("post url worked")
local frameCount = 0
local update

--[[


    """calculate next state of the vehicle"""
    # POST State Values
        x, y, yaw, v = x_t
        steer, accel = v_t

    # WAIT UNTIL SERVER RESPONDS

    # GET Control Respons

    # Convert GET to


--]]



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



    -- STEERING (radians) + ACCEL
    -- ASSUME POSITIVE PI = LEFT, NEGATIVE PI = RIGHT 
    if buttons.Left then
        steering = 0.53
    elseif buttons.Right then
        steering = -0.53
    end

    --- ACCELERATION - Assume accleration based on player input B
    -- Slow down half as fast as accelerate
    if buttons.B then
        acceleration = 22.22
    else
        if velocity > 0 then
            acceleration = -11.11
        else
            accleration = 0
        end
    end

    local current_state = ("X-Pos:" .. tostring(xpos) .. " Y-Pos:" .. tostring(ypos) .. " Yaw:" .. tostring(yaw) .. " Velocity:" .. tostring(velocity) .. " Steering:" .. tostring(steering) .. " Acceleration:" .. acceleration)

    comm.httpPost(postUrl, tostring(current_state))
    update = comm.httpGet(getUrl)

end

while true do
    -- Poll every 60 frames (i.e. every 0.25 seconds)
    if (math.fmod(frameCount, 15) == 0) then
        -- this does all the math
        request()
        -- code to extract steering and accel values
        local steer_pattern = "%p?%d%p%d%d"
        local match_steer = string.find(update, steer_pattern)
        steer_client = tonumber(string.sub(update, match_steer, match_steer + 4))
        -- print("steering = " .. steer_client)
    
        local accel_pattern = "Acceleration:%s*(%-?%d+%.%d%d)"
        local a, b, accel_client = string.find(update, accel_pattern)
        -- print("acceleration = " .. accel_client)
        
    
        -- ACCELERATE CODE
        if tonumber(accel_client) >= -0.20 then
            print("prees B")
            joypad.set({ B = true }, 1)  -- Press B
            local buttons = joypad.get(1)  -- Get current button states
            print(buttons)
        end
    end
    -- grab acceleration
    print("REQUEST FINISHED, BEGIN INPUT SEQUENCE")
    -- print(update)

    frameCount = frameCount + 1
    emu.frameadvance() 
end

