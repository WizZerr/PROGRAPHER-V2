-- LB-01: adapt *verified* v0.2.0 full-recipe Lightroom SDK operations.
-- Manually run, one research CR3 only, allowlisted test catalog only.
-- NO mask modification, autonomous service, real customer catalogs or model code.
local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrExportSession = import 'LrExportSession'
local LrFileUtils = import 'LrFileUtils'
local LrPathUtils = import 'LrPathUtils'
local LrTasks = import 'LrTasks'

local home = LrPathUtils.getStandardFilePath('home')
local researchRoot = LrPathUtils.child(LrPathUtils.child(home, 'Documents'), 'ProGrapher_Research_Private')
local rawFolder = LrPathUtils.child(researchRoot, 'RAW_Parity_Test')
local testCatalog = LrPathUtils.child(LrPathUtils.child(researchRoot, 'ProGrapher_RAW_Test'), 'ProGrapher_RAW_Test.lrcat')
local workdir = LrPathUtils.child(rawFolder, 'BRIDGE_LB01')
local exportDir = LrPathUtils.child(workdir, 'exports')
local jobPath = LrPathUtils.child(workdir, 'job.txt')
local resultPath = LrPathUtils.child(workdir, 'result.txt')
local stage = 'start'
local version = 'lb01-1'

local keys = {
    exposure={-5,5,'Exposure2012'}, contrast={-100,100,'Contrast2012'},
    highlights={-100,100,'Highlights2012'}, shadows={-100,100,'Shadows2012'},
    whites={-100,100,'Whites2012'}, blacks={-100,100,'Blacks2012'},
    vibrance={-100,100,'Vibrance'}, saturation={-100,100,'Saturation'},
    temperature={2000,50000,'Temperature'}, tint={-150,150,'Tint'},
}
local order = {'exposure','contrast','highlights','shadows','whites','blacks',
               'vibrance','saturation','temperature','tint'}

local function norm(path)
    return tostring(path or ''):gsub('/', '\\'):lower()
end
local function normpath(path)
    local p = norm(path)
    if p:find('..', 1, true) then error('SAFETY STOP: noncanonical path') end
    return p
end
local function writeResult(contents)
    local fh, err = io.open(resultPath, 'wb')
    if not fh then error('Cannot write result: '..tostring(err)) end
    fh:write(contents)
    fh:close()
end
local function parseFields(data)
    local fields = {}
    for line in (data..'\n'):gmatch('(.-)\r?\n') do
        if line ~= '' and line:sub(1,1) ~= '#' then
            local key,value = line:match('^([%l%d_]+)=(.+)$')
            if not key or fields[key] ~= nil then error('Invalid/duplicate bridge protocol key') end
            fields[key] = value
        end
    end
    return fields
end
local function readFields(path)
    if LrFileUtils.exists(path) ~= 'file' then error('Missing bridge job/result') end
    local data = LrFileUtils.readFile(path)
    if not data or #data > 8192 then error('Missing/oversized bridge job/result') end
    return parseFields(data)
end
local function parseJob(fields)
    local allowed = {version=true, job_id=true, catalog_path=true, raw_path=true,
                     raw_sha256=true, export_dir=true, profile=true}
    for _,key in ipairs(order) do allowed[key]=true end
    for key in pairs(fields) do
        if not allowed[key] then error('Unrecognized job key') end
    end
    for key in pairs(allowed) do
        if not fields[key] or fields[key] == '' then error('Missing job key: '..key) end
    end
    if fields.version ~= version or #fields.job_id ~= 32 or
        not fields.job_id:match('^[0-9a-f]+$') then
        error('Unsupported bridge job/version')
    end
    if #fields.raw_sha256 ~= 64 or not fields.raw_sha256:match('^[0-9a-f]+$') then
        error('Missing pre-run source fingerprint')
    end
    if normpath(fields.catalog_path) ~= normpath(testCatalog) then
        error('SAFETY STOP: catalog path differs from authorized test catalog')
    end
    if normpath(fields.export_dir) ~= normpath(exportDir) then
        error('SAFETY STOP: export must remain in private test folder')
    end
    if normpath(LrPathUtils.parent(fields.raw_path)) ~= normpath(rawFolder) or
        not normpath(fields.raw_path):match('%.cr3$') then
        error('SAFETY STOP: RAW is not a CR3 in private research RAW folder')
    end
    if fields.profile ~= 'Adobe Standard' then error('Unsupported research profile') end
    for _,key in ipairs(order) do
        local rule=keys[key]
        local value=tonumber(fields[key])
        if not value or value ~= value or value < rule[1] or value > rule[2] then
            error('Unsupported/out-of-range adjustment: '..key)
        end
        fields[key]=value
    end
    return fields
end
local function run()
    stage='verify_allowlist'
    local catalog = LrApplication.activeCatalog()
    if not catalog or normpath(catalog:getPath()) ~= normpath(testCatalog) then
        error('SAFETY STOP: Open exact ProGrapher_RAW_Test.lrcat research COPY only')
    end
    if LrFileUtils.exists(exportDir) ~= 'directory' then
        error('SAFETY STOP: Missing dedicated export folder')
    end
    local fields=parseJob(readFields(jobPath))
    local pending=readFields(resultPath)
    if pending.status ~= 'prepared' or pending.job_id ~= fields.job_id then
        error('SAFETY STOP: Job was already run or its status changed; do not retry')
    end
    if LrFileUtils.exists(fields.raw_path) ~= 'file' then error('Missing test RAW copy') end
    -- SHA-256 pre/post is enforced by Python prepare/verify; SDK Lua cannot hash RAW.
    -- This is a manually invoked POC, NOT an authenticated production IPC layer.

    stage='apply_recipe'
    local photo=catalog:findPhotoByPath(fields.raw_path)
    local recipe={CameraProfile=fields.profile, WhiteBalance='Custom'}
    for _,key in ipairs(order) do recipe[keys[key][3]]=fields[key] end
    catalog:withWriteAccessDo('ProGrapher LB-01 TEST Catalog Recipe', function()
        if not photo then photo=catalog:addPhoto(fields.raw_path) end
        if not photo then error('Could not add research CR3 to test catalog') end
        photo:applyDevelopSettings(recipe,'ProGrapher LB-01')
    end)
    stage='readback'
    local actual=photo:getDevelopSettings()
    if actual.CameraProfile ~= fields.profile then
        error('Profile readback mismatch')
    end
    local output='status=ok\njob_id='..fields.job_id..'\nprofile='..actual.CameraProfile..'\n'
    for _,key in ipairs(order) do
        local r=keys[key]
        local value=actual[r[3]]
        local tol=(key == 'temperature' and 2) or (key == 'tint' and 1) or 0.05
        if type(value) ~= 'number' or math.abs(value-fields[key]) > tol then
            error('Develop readback failed: '..key..'; result='..tostring(value))
        end
        output=output..key..'='..tostring(value)..'\n'
    end

    stage='export_jpeg'
    local session=LrExportSession {
        photosToExport={photo},
        exportSettings={
            LR_exportServiceProvider='com.adobe.ag.export.file',
            LR_format='JPEG', LR_jpeg_quality=1, LR_export_colorSpace='sRGB',
            LR_export_destinationType='specificFolder',
            LR_export_destinationPathPrefix=exportDir,
            LR_export_useSubfolder=false, LR_collisionHandling='rename',
            LR_renamingTokensOn=false, LR_size_doConstrain=false,
            LR_outputSharpeningOn=false, LR_useWatermark=false,
            LR_reimportExportedPhoto=false,
        },
    }
    local jpeg, count=nil,0
    for _,rendition in session:renditions() do
        local ok,pathOrErr=rendition:waitForRender()
        if not ok then error('JPEG export failed: '..tostring(pathOrErr)) end
        jpeg,count=pathOrErr,count+1
    end
    if count ~= 1 or not jpeg or LrFileUtils.exists(jpeg) ~= 'file' or
        normpath(LrPathUtils.parent(jpeg)) ~= normpath(exportDir) then
        error('JPEG missing or outside expected test export folder')
    end
    local attr=LrFileUtils.fileAttributes(jpeg)
    if not attr or not attr.fileSize or attr.fileSize < 1024 then
        error('Invalid rendered JPEG size')
    end
    stage='write_result'
    writeResult(output..'jpeg='..jpeg..'\nbytes='..tostring(attr.fileSize)..'\n')
    LrDialogs.message('ProGrapher LB-01 — Research PASS',
        'Recipe values read back; Lightroom exported one JPEG.\nRun Python verify for RAW hash and JPEG signature.', 'info')
end

LrTasks.startAsyncTask(function()
    local ok,err=LrTasks.pcall(run)
    if not ok then
        local message=tostring(err):gsub('[\r\n]',' ')
        pcall(function()
            writeResult('status=error\nstage='..stage..'\nerror='..message..'\n')
        end)
        LrDialogs.message('ProGrapher LB-01 — STOPPED', message, 'critical')
    end
end)
