-- SP-01 isolated RESEARCH adapter: export a PREPARED neutral virtual copy
-- and separately snapshot original master Develop values. This script NEVER
-- creates/resets/develops a copy, and NEVER edits the photographer's catalog.
-- One exact authorized disposable catalog, one selected virtual copy only.
local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrExportSession = import 'LrExportSession'
local LrFileUtils = import 'LrFileUtils'
local LrPathUtils = import 'LrPathUtils'
local LrTasks = import 'LrTasks'

local home = LrPathUtils.getStandardFilePath('home')
local root = LrPathUtils.child(LrPathUtils.child(home, 'Documents'), 'ProGrapher_Research_Private')
local study = LrPathUtils.child(root, 'SP_01_Catalog_Test')
local catalogFolder = LrPathUtils.child(study, 'SP_01_OFFLINE_PROOF')
local allowedCatalog = LrPathUtils.child(catalogFolder, 'SP_01_OFFLINE_PROOF.lrcat')
local exportDir = LrPathUtils.child(catalogFolder, 'SP_01_PLUGIN_EXPORTS')
local targetPath = LrPathUtils.child(exportDir, 'SP01_DEVELOP_TARGET_PRIVATE.txt')

local function norm(path)
    local p = tostring(path or ''):gsub('/', '\\'):lower()
    if p:find('..', 1, true) then error('SAFETY STOP: noncanonical path') end
    return p
end

local function printable(value)
    if type(value) == 'number' then
        if value ~= value then return 'UNSUPPORTED' end
        return tostring(value)
    end
    if type(value) == 'boolean' then return tostring(value) end
    if type(value) == 'string' then return value:gsub('[\r\n=]', ' ') end
    if value == nil then return 'MISSING' end
    return 'UNSUPPORTED_COMPLEX'
end

local TARGET_FIELDS = {
    'CameraProfile', 'ProcessVersion', 'WhiteBalance',
    'Exposure2012', 'Contrast2012', 'Highlights2012', 'Shadows2012',
    'Whites2012', 'Blacks2012', 'Clarity2012', 'Vibrance', 'Saturation',
    'Temperature', 'Tint', 'CropLeft', 'CropTop', 'CropRight',
    'CropBottom', 'CropAngle', 'CropConstrainToWarp',
}

local function run()
    local catalog = LrApplication.activeCatalog()
    if not catalog or norm(catalog:getPath()) ~= norm(allowedCatalog) then
        error('SAFETY STOP: Open only SP_01_OFFLINE_PROOF.lrcat disposable research copy')
    end
    if LrFileUtils.exists(exportDir) ~= 'directory' then
        error('SAFETY STOP: Create SP_01_PLUGIN_EXPORTS folder inside copied catalog first')
    end
    if LrFileUtils.exists(targetPath) then
        error('SAFETY STOP: Prior SP01 evidence exists; do not overwrite')
    end
    local selected = catalog:getTargetPhotos()
    if #selected ~= 1 then error('Select exactly ONE prepared/reset virtual copy') end
    local neutralCopy = selected[1]
    if neutralCopy:getRawMetadata('isVirtualCopy') ~= true then
        error('SAFETY STOP: Select the RESET Virtual Copy, not the photographer original')
    end
    local original = neutralCopy:getRawMetadata('masterPhoto')
    if not original or original:getRawMetadata('isVirtualCopy') == true then
        error('SAFETY STOP: missing/unexpected master photo identity')
    end
    if neutralCopy:checkPhotoAvailability() or original:checkPhotoAvailability() then
        error('SAFETY STOP: physical RAW copy must be OFFLINE for this Smart Preview proof')
    end
    if neutralCopy:getRawMetadata('isCropped') then
        error('SAFETY STOP: neutral research copy still has a Crop')
    end
    local copyUUID = printable(neutralCopy:getRawMetadata('uuid'))
    local masterUUID = printable(original:getRawMetadata('uuid'))
    if copyUUID == 'MISSING' or masterUUID == 'MISSING' or copyUUID == masterUUID then
        error('SAFETY STOP: invalid or ambiguous master/virtual-copy UUID')
    end

    -- Master is READ ONLY; target extraction is separate from the model input.
    local originalDevelop = original:getDevelopSettings()
    local copyDevelop = neutralCopy:getDevelopSettings()
    if not originalDevelop or not copyDevelop then error('Develop readback unavailable') end
    -- This partial check does not establish full neutral-input anti-leakage.
    if math.abs(tonumber(copyDevelop.Exposure2012) or 1000) > 0.01 then
        error('SAFETY STOP: selected virtual copy does not resemble a Reset baseline')
    end
    local fields = {
        'schema=prographer.sp01.master_target_research.v0',
        'status=UNAPPROVED_RESEARCH_ONLY',
        'training_ready=false',
        'neutral_input_leakage_independently_verified=false',
        'raw_offline_preflight=true',
        'copy_uuid='..copyUUID,
        'master_uuid='..masterUUID,
        'master_has_opaque_masks='..tostring(type(originalDevelop.MaskGroupBasedCorrections) == 'table'),
        'master_recipe_COMPLETENESS=PARTIAL_UNSUPPORTED_FIELDS_REQUIRE_REVIEW',
    }
    for _, key in ipairs(TARGET_FIELDS) do
        fields[#fields + 1] = 'target_'..key..'='..printable(originalDevelop[key])
    end
    -- Only export selected VC. No Lightroom catalog modifications at any step.
    local session = LrExportSession {
        photosToExport = { neutralCopy },
        exportSettings = {
            LR_exportServiceProvider = 'com.adobe.ag.export.file',
            LR_format = 'JPEG', LR_jpeg_quality = 1,
            LR_export_colorSpace = 'sRGB',
            LR_export_destinationType = 'specificFolder',
            LR_export_destinationPathPrefix = exportDir,
            LR_export_useSubfolder = false,
            LR_collisionHandling = 'rename',
            LR_renamingTokensOn = false, LR_size_doConstrain = false,
            LR_outputSharpeningOn = false, LR_useWatermark = false,
            LR_reimportExportedPhoto = false,
        },
    }
    local jpg, count = nil, 0
    for _, rendition in session:renditions() do
        local ok, value = rendition:waitForRender()
        if not ok then error('Neutral JPEG export failed') end
        jpg, count = value, count + 1
    end
    if count ~= 1 or not jpg or LrFileUtils.exists(jpg) ~= 'file' or
       norm(LrPathUtils.parent(jpg)) ~= norm(exportDir) then
        error('Export missing or escaped authorized output folder')
    end
    local attrs = LrFileUtils.fileAttributes(jpg)
    if not attrs or not attrs.fileSize or attrs.fileSize < 1024 then
        error('JPEG invalid size')
    end
    fields[#fields + 1] = 'neutral_jpeg_PRIVATE='..printable(jpg)
    fields[#fields + 1] = 'neutral_bytes='..tostring(attrs.fileSize)
    -- Evidence remains private; no photographic pixels, paths or IDs in GitHub.
    local fh, err = io.open(targetPath, 'wb')
    if not fh then error('Cannot write private research target snapshot: '..tostring(err)) end
    fh:write(table.concat(fields, '\n')..'\n')
    fh:close()
    LrDialogs.message('ProGrapher SP-01 research export',
        'ONE reset virtual copy exported with ORIGINAL master target snapshot.\n'..
        'Neutrality/anti-leakage NOT yet proven; no training.', 'info')
end

LrTasks.startAsyncTask(function()
    local ok, err = LrTasks.pcall(run)
    if not ok then
        LrDialogs.message('ProGrapher SP-01 — STOPPED', tostring(err), 'critical')
    end
end)
