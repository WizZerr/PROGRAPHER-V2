-- SP-AUTO-01 Lightroom Classic SDK auto worker — RESEARCH ONLY.
-- Only SP_01_OFFLINE_PROOF.lrcat in the user's research tree is permitted.
-- Mutates ONLY its disposable catalog: creates one VC, resets that VC, exports.
-- Never applies or resets Develop on the master. No customer catalog support.
local LrApplication = import 'LrApplication'
local LrApplicationView = import 'LrApplicationView'
local LrDevelopController = import 'LrDevelopController'
local LrExportSession = import 'LrExportSession'
local LrFileUtils = import 'LrFileUtils'
local LrPathUtils = import 'LrPathUtils'
local LrTasks = import 'LrTasks'

local home = LrPathUtils.getStandardFilePath('home')
local root = LrPathUtils.child(LrPathUtils.child(home, 'Documents'), 'ProGrapher_Research_Private')
local study = LrPathUtils.child(root, 'SP_01_Catalog_Test')
local folder = LrPathUtils.child(study, 'SP_01_OFFLINE_PROOF')
local catalogPath = LrPathUtils.child(folder, 'SP_01_OFFLINE_PROOF.lrcat')
local smartDir = LrPathUtils.child(folder, 'SP_01_OFFLINE_PROOF Smart Previews.lrdata')
local workdir = LrPathUtils.child(folder, 'SP_01_AUTO_BRIDGE')
local exports = LrPathUtils.child(workdir, 'exports')
local jobPath = LrPathUtils.child(workdir, 'job.txt')
local resultPath = LrPathUtils.child(workdir, 'result.txt')
local targetPath = LrPathUtils.child(workdir, 'master_target_PRIVATE.txt')

local VERSION = 'spauto01-1'
local OPERATION = 'EXTRACT_NEUTRAL_SMART_PREVIEW'
local SELECTION = 'EXACTLY_ONE_MASTER_IN_DISPOSABLE_CATALOG'
local NEUTRAL_POLICY = 'lightroom-reset-defaults-v1-UNVERIFIED'
local processing = false
local watcherRunning = false

local function norm(path)
    local value = tostring(path or ''):gsub('/', '\\'):lower()
    if value:find('..', 1, true) then error('SAFETY STOP: path traversal') end
    return value
end

local function readFields(path)
    if LrFileUtils.exists(path) ~= 'file' then error('Protocol file not found') end
    local data = LrFileUtils.readFile(path)
    if not data or #data > 8192 then error('Invalid protocol size') end
    local fields = {}
    for line in (data..'\n'):gmatch('(.-)\r?\n') do
        if line ~= '' then
            local k, v = line:match('^([a-z][a-z0-9_]*)=(.+)$')
            if not k or fields[k] or v:find('[\r\n]') then
                error('Malformed/repeated bridge protocol field')
            end
            fields[k] = v
        end
    end
    return fields
end

local function writeResult(data)
    local fh, err = io.open(resultPath, 'wb')
    if not fh then error('Cannot write SP-AUTO-01 result: '..tostring(err)) end
    fh:write(data)
    fh:close()
end

local function kv(fields)
    local parts = {}
    for _, pair in ipairs(fields) do
        local k, v = pair[1], tostring(pair[2])
        if not k:match('^[a-z][a-z0-9_]*$') or v == '' or v:find('[\r\n]') then
            error('Invalid result field')
        end
        parts[#parts + 1] = k..'='..v
    end
    return table.concat(parts, '\n')..'\n'
end

local function stableSettings(value, seen, depth)
    -- Fail closed for cycles/opaque objects. Strict target hash is research-only:
    -- Lightroom may create version-dependent opaque Develop values.
    if depth > 12 then error('Nested Develop structure too deep') end
    local t = type(value)
    if t == 'nil' then return 'nil' end
    if t == 'number' or t == 'boolean' or t == 'string' then
        return t..':'..tostring(value)
    end
    if t ~= 'table' or seen[value] then
        error('Opaque or circular Develop value')
    end
    seen[value] = true
    local keys = {}
    for k in pairs(value) do keys[#keys + 1] = k end
    table.sort(keys, function(a,b) return tostring(a) < tostring(b) end)
    local parts = {}
    for _, k in ipairs(keys) do
        parts[#parts+1] = stableSettings(k, seen, depth+1)..':'..
            stableSettings(value[k], seen, depth+1)
    end
    seen[value] = nil
    return '{'..table.concat(parts, ',')..'}'
end

local function fingerprint(photo)
    local settings = photo:getDevelopSettings()
    if type(settings) ~= 'table' then error('Missing master Develop settings') end
    return stableSettings(settings, {}, 0), settings
end

local function printable(value)
    if value == nil then return 'MISSING' end
    if type(value) ~= 'number' and type(value) ~= 'boolean'
        and type(value) ~= 'string' then return 'COMPLEX_REQUIRES_REVIEW' end
    return tostring(value):gsub('[\r\n=]', ' ')
end

local TARGET_FIELDS = {
    'CameraProfile', 'ProcessVersion', 'WhiteBalance', 'Exposure2012',
    'Contrast2012', 'Highlights2012', 'Shadows2012', 'Whites2012',
    'Blacks2012', 'Clarity2012', 'Vibrance', 'Saturation',
    'Temperature', 'Tint', 'CropLeft', 'CropTop', 'CropRight',
    'CropBottom', 'CropAngle',
}

local function run()
    local job = readFields(jobPath)
    local state = readFields(resultPath)
    local allowed = {
        version=true, job_id=true, catalog_path=true, export_dir=true,
        operation=true, selection_policy=true, neutral_policy=true,
    }
    for k in pairs(job) do if not allowed[k] then error('Unknown job field') end end
    for k in pairs(allowed) do if not job[k] then error('Missing job field') end end
    if job.version ~= VERSION or #job.job_id ~= 32
        or not job.job_id:match('^[0-9a-f]+$')
        or job.operation ~= OPERATION
        or job.selection_policy ~= SELECTION
        or job.neutral_policy ~= NEUTRAL_POLICY
        or norm(job.catalog_path) ~= norm(catalogPath)
        or norm(job.export_dir) ~= norm(exports)
        or state.status ~= 'prepared' or state.job_id ~= job.job_id then
        error('SAFETY STOP: unsupported/stale/redirected research job')
    end
    -- One-time claim. Even if Lightroom crashes, never automatically replay.
    writeResult(kv({{'status','running'}, {'job_id',job.job_id}}))
    local stage = 'preflight'

    local function work()
        local catalog = LrApplication.activeCatalog()
        if not catalog or norm(catalog:getPath()) ~= norm(catalogPath) then
            error('SAFETY STOP: not the exact research catalog')
        end
        if LrFileUtils.exists(smartDir) ~= 'directory'
            or LrFileUtils.exists(exports) ~= 'directory'
            or LrFileUtils.exists(targetPath) then
            error('SAFETY STOP: research store/output invalid or already used')
        end
        local entries = LrFileUtils.files(exports) or {}
        -- LrFileUtils.files() returns an iterator in some Lightroom releases:
        -- use an explicit destination existence check before and after export.
        if type(entries) == 'table' and next(entries) then
            error('SAFETY STOP: export folder not empty')
        end

        stage = 'find_master'
        local masters = {}
        for _, photo in ipairs(catalog:getAllPhotos()) do
            if photo:getRawMetadata('isVirtualCopy') ~= true then
                masters[#masters+1] = photo
            end
        end
        if #masters ~= 1 then
            error('SAFETY STOP: expected exactly one master in disposable catalog')
        end
        local master = masters[1]
        local uuid = master:getRawMetadata('uuid')
        local info = master:getRawMetadata('smartPreviewInfo')
        if not uuid or type(uuid) ~= 'string' or
            type(info) ~= 'table' or not info.smartPreviewSize or info.smartPreviewSize <= 0 or
            master:checkPhotoAvailability() then
            error('SAFETY STOP: source identity, offline RAW, or Smart Preview invalid')
        end
        local sourcePath = master:getRawMetadata('path')
        if not sourcePath or LrFileUtils.exists(sourcePath) == 'file' then
            error('SAFETY STOP: physical original is available')
        end
        local originalFingerprint, originalSettings = fingerprint(master)

        -- Private RESEARCH evidence first; contains no image pixels and never
        -- goes to GitHub. This is intentionally a partial target recipe.
        stage = 'snapshot_master'
        local lines = {
            'schema=prographer.spauto01.master_target.v0',
            'job_id='..job.job_id,
            'master_uuid='..printable(uuid),
            'photographer_target_training_approved=false',
            'full_develop_target_verified=false',
        }
        for _, key in ipairs(TARGET_FIELDS) do
            lines[#lines+1] = 'target_'..key..'='..printable(originalSettings[key])
        end
        local targetFile = io.open(targetPath, 'wb')
        if not targetFile then error('Cannot create private target snapshot') end
        targetFile:write(table.concat(lines, '\n')..'\n')
        targetFile:close()

        -- Create from master without user selecting photo manually.
        -- SDK createVirtualCopies works on selected pictures and is async-task only.
        stage = 'create_virtual_copy'
        catalog:setActiveSources(catalog.kAllPhotos)
        catalog:setSelectedPhotos(master, {})
        if catalog:getTargetPhoto() ~= master then
            error('SAFETY STOP: unable to select exact master')
        end
        local selected = catalog:getTargetPhotos()
        if #selected ~= 1 or selected[1] ~= master then
            error('SAFETY STOP: ambiguous Lightroom selection')
        end
        local created = catalog:createVirtualCopies('SP01_AUTO_'..job.job_id:sub(1,8))
        if type(created) ~= 'table' or #created ~= 1 then
            error('SAFETY STOP: virtual copy creation not confirmed')
        end
        local copy = created[1]
        if copy == master or copy:getRawMetadata('isVirtualCopy') ~= true
            or copy:getRawMetadata('masterPhoto') ~= master then
            error('SAFETY STOP: copy/master identity mismatch')
        end
        local copyUuid = copy:getRawMetadata('uuid')
        if not copyUuid or copyUuid == uuid then
            error('SAFETY STOP: ambiguous virtual copy UUID')
        end

        stage = 'develop_reset'
        catalog:setSelectedPhotos(copy, {})
        LrApplicationView.switchToModule('develop')
        local selectedCopy = false
        for _ = 1, 25 do
            LrTasks.sleep(0.25)
            if LrApplicationView.getCurrentModuleName() == 'develop'
                and catalog:getTargetPhoto() == copy then
                selectedCopy = true
                break
            end
        end
        if not selectedCopy then
            error('SAFETY STOP: Develop current-photo guard failed; Reset NOT attempted')
        end
        if catalog:getTargetPhoto() ~= copy or copy:getRawMetadata('masterPhoto') ~= master then
            error('SAFETY STOP: current photo changed before Reset')
        end
        LrDevelopController.resetAllDevelopAdjustments()
        LrTasks.sleep(1.5)
        if catalog:getTargetPhoto() ~= copy then
            error('SAFETY STOP: photo selection changed after Reset')
        end
        -- Explicitly restore full uncropped scene, on the verified copy ONLY.
        if copy:getRawMetadata('isCropped') == true then
            LrDevelopController.resetCrop()
            LrTasks.sleep(0.7)
        end
        local neutral = copy:getDevelopSettings()
        local exposure = neutral and tonumber(neutral.Exposure2012)
        if not exposure or math.abs(exposure) > 0.01
            or copy:getRawMetadata('isCropped') == true then
            error('SAFETY STOP: neutral reset readback failed')
        end
        if copy:checkPhotoAvailability() then
            error('SAFETY STOP: original RAW became available')
        end
        if fingerprint(master) ~= originalFingerprint then
            error('SAFETY STOP: master Develop changed unexpectedly')
        end

        stage = 'export_neutral'
        local session = LrExportSession {
            photosToExport = {copy},
            exportSettings = {
                LR_exportServiceProvider = 'com.adobe.ag.export.file',
                LR_format = 'JPEG', LR_jpeg_quality = 1,
                LR_export_colorSpace = 'sRGB',
                LR_export_destinationType = 'specificFolder',
                LR_export_destinationPathPrefix = exports,
                LR_export_useSubfolder = false,
                LR_collisionHandling = 'skip',
                LR_renamingTokensOn = false, LR_size_doConstrain = false,
                LR_outputSharpeningOn = false, LR_useWatermark = false,
                LR_reimportExportedPhoto = false,
            },
        }
        local jpeg, count = nil, 0
        for _, rendition in session:renditions() do
            local ok, outOrErr = rendition:waitForRender()
            if not ok then error('SDK neutral JPEG export failed') end
            jpeg, count = outOrErr, count+1
        end
        if count ~= 1 or not jpeg or
            LrFileUtils.exists(jpeg) ~= 'file' or
            norm(LrPathUtils.parent(jpeg)) ~= norm(exports) then
            error('SAFETY STOP: missing/redirected JPEG export')
        end
        local attrs = LrFileUtils.fileAttributes(jpeg)
        if not attrs or not attrs.fileSize or attrs.fileSize < 1024 then
            error('Export too small or unavailable')
        end
        if fingerprint(master) ~= originalFingerprint then
            error('SAFETY STOP: original master Develop changed during export')
        end
        stage = 'success'
        writeResult(kv({
            {'status','ok'}, {'job_id',job.job_id},
            {'jpeg',jpeg}, {'bytes',attrs.fileSize},
            {'master_uuid',uuid}, {'copy_uuid',copyUuid},
            {'raw_offline','true'}, {'smart_preview','true'},
            {'master_develop_unchanged','true'},
            {'neutral_exposure',exposure}, {'neutral_cropped','false'},
            {'target_snapshot',targetPath},
        }))
    end

    local ok, err = LrTasks.pcall(work)
    if not ok then
        -- No automatic replay or cleanup: preserve disposable catalog evidence.
        local why = tostring(err):gsub('[\r\n=]', ' ')
        pcall(function()
            writeResult(kv({
                {'status','error'}, {'job_id',job.job_id},
                {'stage',stage}, {'error',why:sub(1,200)},
            }))
        end)
    end
end

local M = {}
function M.start()
    if watcherRunning then return end
    watcherRunning = true
    LrTasks.startAsyncTask(function()
        while watcherRunning do
            local hasJob = LrFileUtils.exists(jobPath) == 'file'
            local hasState = LrFileUtils.exists(resultPath) == 'file'
            if hasJob and hasState and not processing then
                -- Only work for the exact research catalog.
                local catalog = LrApplication.activeCatalog()
                if catalog and norm(catalog:getPath()) == norm(catalogPath) then
                    local ok, state = LrTasks.pcall(readFields, resultPath)
                    if ok and state.status == 'prepared' then
                        processing = true
                        LrTasks.pcall(run)
                        processing = false
                    end
                end
            end
            LrTasks.sleep(3)
        end
    end)
end
function M.stop()
    watcherRunning = false
end
return M
