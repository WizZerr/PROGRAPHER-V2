-- SP-AUTO-01 Lightroom Classic SDK counterfactual two-VC worker — RESEARCH ONLY.
-- Only SP_01_AUTO_LEAK_01.lrcat in the user's research tree is permitted.
-- Mutates ONLY its disposable catalog: two VCs and perturb B only; never master.
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
local folder = LrPathUtils.child(study, 'SP_01_AUTO_LEAK_01')
local catalogPath = LrPathUtils.child(folder, 'SP_01_AUTO_LEAK_01.lrcat')
local smartDir = LrPathUtils.child(folder, 'SP_01_AUTO_LEAK_01 Smart Previews.lrdata')
local workdir = LrPathUtils.child(folder, 'SP_03_BRIDGE')
local exports = LrPathUtils.child(workdir, 'exports')
local exportA = LrPathUtils.child(exports, 'A')
local exportB = LrPathUtils.child(exports, 'B')
local exportP = LrPathUtils.child(exports, 'P')
local jobPath = LrPathUtils.child(workdir, 'job.txt')
local resultPath = LrPathUtils.child(workdir, 'result.txt')
local targetPath = LrPathUtils.child(workdir, 'master_target_PRIVATE.txt')

local VERSION = 'spauto03-1'
local OPERATION = 'COUNTERFACTUAL_VC_RESET'
local SELECTION = 'ONE_OFFLINE_MASTER_ZERO_COPIES'
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
        if LrFileUtils.exists(exportA) ~= 'directory'
            or LrFileUtils.exists(exportB) ~= 'directory'
            or LrFileUtils.exists(exportP) ~= 'directory'
            or not LrFileUtils.isEmptyDirectory(exportA)
            or not LrFileUtils.isEmptyDirectory(exportB)
            or not LrFileUtils.isEmptyDirectory(exportP) then
            error('SAFETY STOP: two fresh empty variant export folders required')
        end

        stage = 'find_master'
        local allPhotos = catalog:getAllPhotos()
        -- This run is deliberately FROM SCRATCH. The photographer confirmed
        -- that every previous research VC was deleted before catalog cloning.
        -- Abort if a stale VC was included; no implicit reuse or cleanup.
        if #allPhotos ~= 1 then
            error('SAFETY STOP: E2E catalog must contain exactly one master and no Virtual Copies')
        end
        local masters = {}
        for _, photo in ipairs(allPhotos) do
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
        -- Full nested Develop snapshot is private research data. Not parsed by
        -- the model, and not claimed to be a fully supported training recipe.
        lines[#lines+1] = 'full_develop_serialized_PRIVATE='..
            originalFingerprint:gsub('[\r\n]', ' ')
        local targetFile = io.open(targetPath, 'wb')
        if not targetFile then error('Cannot create private target snapshot') end
        targetFile:write(table.concat(lines, '\n')..'\n')
        targetFile:close()


        -- Counterfactual study: two UNIQUE copies from the same offline master.
        -- Only the disposable VCs are changed. Never applyDevelopSettings on master.
        stage = 'create_two_virtual_copies'
        catalog:setActiveSources(catalog.kAllPhotos)
        local function createCopy(label)
            catalog:setSelectedPhotos(master, {})
            if catalog:getTargetPhoto() ~= master then
                error('SAFETY STOP: master is not current')
            end
            local selected = catalog:getTargetPhotos()
            if #selected ~= 1 or selected[1] ~= master then
                error('SAFETY STOP: ambiguous master selection')
            end
            local created = catalog:createVirtualCopies(label..'_'..job.job_id:sub(1,8))
            if type(created) ~= 'table' or #created ~= 1 then
                error('SP03_VIRTUAL_COPY_CREATE_FAILED')
            end
            local copy = created[1]
            if copy == master or copy:getRawMetadata('isVirtualCopy') ~= true
                or copy:getRawMetadata('masterPhoto') ~= master then
                error('SP03_VIRTUAL_COPY_IDENTITY_FAILED')
            end
            return copy
        end
        local copyA = createCopy('SP03_A')
        local copyB = createCopy('SP03_B')
        local uuidA = copyA:getRawMetadata('uuid')
        local uuidB = copyB:getRawMetadata('uuid')
        if copyA == copyB or not uuidA or not uuidB
            or uuidA == uuidB or uuidA == uuid or uuidB == uuid then
            error('SP03_VC_UUID_COLLISION')
        end
        local beforeA, settingsA = fingerprint(copyA)
        if beforeA ~= originalFingerprint then
            error('SP03_A_DID_NOT_INHERIT_MASTER_DEVELOP')
        end
        local ex = tonumber(settingsA.Exposure2012)
        local highlights = tonumber(settingsA.Highlights2012)
        if not ex or not highlights then
            error('SP03_MASTER_DEVELOP_NUMERICAL_FIELDS_MISSING')
        end
        -- Counterfactual input differs significantly in at least TWO dimensions.
        -- Clamp stays within Lightroom basic sliders' legal ranges.
        local exposureB = ex < 2.0 and ex + 1.75 or ex - 1.75
        local highlightsB = highlights < 45 and highlights + 45 or highlights - 45
        if exposureB < -4.0 or exposureB > 4.0
            or highlightsB < -100 or highlightsB > 100 then
            error('SP03_PERTURBATION_OUT_OF_RANGE')
        end

        stage = 'perturb_copy_b'
        catalog:withWriteAccessDo('SP03 Private Counterfactual B VC Only', function()
            copyB:applyDevelopSettings({
                Exposure2012 = exposureB,
                Highlights2012 = highlightsB,
            }, 'SP03 deliberate VC-only counterfactual')
        end)
        local beforeB, checkedB = nil, nil
        for _ = 1, 40 do
            LrTasks.sleep(0.25)
            beforeB, checkedB = fingerprint(copyB)
            if beforeB ~= beforeA
                and tonumber(checkedB.Exposure2012)
                and tonumber(checkedB.Highlights2012)
                and math.abs(tonumber(checkedB.Exposure2012) - exposureB) < 0.02
                and math.abs(tonumber(checkedB.Highlights2012) - highlightsB) < 0.5 then
                break
            end
        end
        if beforeB == beforeA
            or math.abs((tonumber(checkedB.Exposure2012) or 1000) - exposureB) > 0.02
            or math.abs((tonumber(checkedB.Highlights2012) or 1000) - highlightsB) > 0.5 then
            error('SP03_PERTURBATION_NOT_COMMITTED_OR_READBACK_BAD')
        end
        if fingerprint(master) ~= originalFingerprint then
            error('SP03_MASTER_CHANGED_DURING_PERTURBATION')
        end

        local function exportOne(copy, dest, which)
            stage = 'export_'..which
            local session = LrExportSession {
                photosToExport = {copy},
                exportSettings = {
                    LR_exportServiceProvider = 'com.adobe.ag.export.file',
                    LR_format = 'JPEG', LR_jpeg_quality = 1,
                    LR_export_colorSpace = 'sRGB',
                    LR_export_destinationType = 'specificFolder',
                    LR_export_destinationPathPrefix = dest,
                    LR_export_useSubfolder = false,
                    LR_collisionHandling = 'skip',
                    LR_renamingTokensOn = false, LR_size_doConstrain = false,
                    LR_outputSharpeningOn = false, LR_useWatermark = false,
                    LR_reimportExportedPhoto = false,
                },
            }
            local jpeg, count = nil, 0
            for _, rendition in session:renditions() do
                local rendered, out = rendition:waitForRender()
                if not rendered then error('SP03_JPEG_EXPORT_FAILED_'..which) end
                jpeg, count = out, count + 1
            end
            if count ~= 1 or not jpeg or LrFileUtils.exists(jpeg) ~= 'file'
                or norm(LrPathUtils.parent(jpeg)) ~= norm(dest) then
                error('SP03_EXPORT_PATH_OR_COUNT_BAD_'..which)
            end
            local attrs = LrFileUtils.fileAttributes(jpeg)
            if not attrs or not attrs.fileSize or attrs.fileSize < 1024 then
                error('SP03_EXPORT_TOO_SMALL_'..which)
            end
            if fingerprint(master) ~= originalFingerprint then
                error('SP03_MASTER_CHANGED_AFTER_EXPORT_'..which)
            end

            return jpeg
        end

        local function resetExportOne(copy, dest, which)
            -- Reset only after 3 consecutive controller/photo readback matches.
            stage = 'develop_ready_'..which
            catalog:setSelectedPhotos(copy, {})
            LrApplicationView.switchToModule('develop')
            local ready, stable = false, 0
            for _ = 1, 100 do
                LrTasks.sleep(0.25)
                if LrApplicationView.getCurrentModuleName() == 'develop'
                    and catalog:getTargetPhoto() == copy
                    and copy:getRawMetadata('masterPhoto') == master then
                    local okEx, uiEx = LrTasks.pcall(LrDevelopController.getValue, 'Exposure')
                    local okHi, uiHi = LrTasks.pcall(LrDevelopController.getValue, 'Highlights')
                    local current = copy:getDevelopSettings()
                    local ownEx = current and tonumber(current.Exposure2012)
                    local ownHi = current and tonumber(current.Highlights2012)
                    if okEx and okHi and type(uiEx) == 'number'
                        and type(uiHi) == 'number'
                        and ownEx and ownHi
                        and math.abs(uiEx - ownEx) < 0.05
                        and math.abs(uiHi - ownHi) < 0.5 then
                        stable = stable + 1
                    else
                        stable = 0
                    end
                    if stable >= 3 then ready = true break end
                else
                    stable = 0
                end
            end
            if not ready then error('SP03_DEVELOP_CONTROLLER_NOT_READY_'..which) end
            local before = fingerprint(copy)
            stage = 'reset_'..which
            LrDevelopController.resetAllDevelopAdjustments()
            local changed = false
            for _ = 1, 64 do
                LrTasks.sleep(0.25)
                if catalog:getTargetPhoto() ~= copy
                    or LrApplicationView.getCurrentModuleName() ~= 'develop'
                    or copy:getRawMetadata('masterPhoto') ~= master then
                    error('SP03_SELECTION_CHANGED_DURING_RESET_'..which)
                end
                if fingerprint(copy) ~= before then
                    changed = true
                    break
                end
            end
            if not changed then error('SP03_RESET_NO_CHANGE_'..which) end
            if copy:getRawMetadata('isCropped') == true then
                stage = 'crop_'..which
                LrDevelopController.resetCrop()
                for _ = 1, 40 do
                    LrTasks.sleep(0.25)
                    if catalog:getTargetPhoto() ~= copy then
                        error('SP03_SELECTION_CHANGED_DURING_CROP_'..which)
                    end
                    if copy:getRawMetadata('isCropped') ~= true then break end
                end
            end
            local postFingerprint, postSettings = fingerprint(copy)
            local exposure = postSettings and tonumber(postSettings.Exposure2012)
            if not exposure or math.abs(exposure) > 0.01
                or copy:getRawMetadata('isCropped') == true then
                error('SP03_RESET_NOT_NEUTRAL_'..which)
            end
            if copy:checkPhotoAvailability() or fingerprint(master) ~= originalFingerprint then
                error('SP03_SOURCE_MASTER_CHANGED_OR_BECAME_AVAILABLE_'..which)
            end

            local jpeg = exportOne(copy, dest, which)
            return postFingerprint, exposure, jpeg
        end

        -- Confirm deliberately altered VC B actually renders different pixels
        -- before reset. Python compares P to A/B after all three exports.
        if fingerprint(copyB) ~= beforeB then
            error('SP03_PERTURBATION_CHANGED_BEFORE_EXPORT')
        end
        local jpegPerturbed = exportOne(copyB, exportP, 'P')
        local neutralA, exposureA, jpegA = resetExportOne(copyA, exportA, 'A')
        local neutralB, exposureBReset, jpegB = resetExportOne(copyB, exportB, 'B')
        stage = 'full_develop_comparison'
        if neutralA ~= neutralB then
            error('SP03_FULL_POST_RESET_DEVELOP_MISMATCH')
        end
        if fingerprint(master) ~= originalFingerprint then
            error('SP03_MASTER_CHANGED_AT_FINAL_GATE')
        end
        if LrFileUtils.exists(jpegA) ~= 'file' or LrFileUtils.exists(jpegB) ~= 'file'
            or LrFileUtils.exists(jpegPerturbed) ~= 'file' then
            error('SP03_OUTPUT_DISAPPEARED')
        end

        stage = 'success'
        writeResult(kv({
            {'status','ok'}, {'job_id',job.job_id},
            {'jpeg_a',jpegA}, {'jpeg_b',jpegB},
            {'jpeg_perturbed',jpegPerturbed},
            {'master_uuid',uuid}, {'copy_a_uuid',uuidA}, {'copy_b_uuid',uuidB},
            {'target_fingerprint_unchanged','true'},
            {'pre_reset_variants_distinct','true'},
            {'post_reset_full_develop_equal','true'},
            {'post_reset_exposure_a',exposureA},
            {'post_reset_exposure_b',exposureBReset},
            {'post_reset_uncropped_a','true'},
            {'post_reset_uncropped_b','true'},
            {'source_raw_offline','true'}, {'smart_preview_present','true'},
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
