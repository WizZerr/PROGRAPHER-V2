-- PG-LI-02B.01 — read-only, explicitly selected photo identity export.
-- Does NOT change the Lightroom catalog, original photo, XMP or Smart Preview.
-- Research only: no unattended/background worker. Save output locally only.
local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrFileUtils = import 'LrFileUtils'
local LrTasks = import 'LrTasks'

local function q(value)
    if type(value) ~= 'string' then return 'null' end
    local chars = {'"'}
    for i = 1, #value do
        local n = value:byte(i)
        if n == 34 then chars[#chars + 1] = '\\"'
        elseif n == 92 then chars[#chars + 1] = '\\\\'
        elseif n < 32 then chars[#chars + 1] = string.format('\\u%04x', n)
        else chars[#chars + 1] = string.char(n)
        end
    end
    chars[#chars + 1] = '"'
    return table.concat(chars)
end

local function run()
    local catalog = LrApplication.activeCatalog()
    if not catalog then error('Open the authorized research catalog in Lightroom.') end

    local selected = catalog:getTargetPhotos()
    if type(selected) ~= 'table' or #selected < 1 or #selected > 16 then
        error('Select 1 to 16 research photos in the Lightroom Library first.')
    end

    local rows = {}
    for _, photo in ipairs(selected) do
        local uuid = photo:getRawMetadata('uuid')
        local info = photo:getRawMetadata('smartPreviewInfo')
        local path = (type(info) == 'table') and info.smartPreviewPath or nil
        local virtual = photo:getRawMetadata('isVirtualCopy')
        if type(uuid) ~= 'string' or #uuid > 128 or uuid == '' then
            error('Lightroom did not provide a photo UUID; export aborted.')
        end
        rows[#rows + 1] = '{' ..
            '"photo_uuid":' .. q(uuid) .. ',' ..
            '"smart_preview_path":' .. q(path) .. ',' ..
            '"is_virtual_copy":' .. tostring(virtual == true) ..
            '}'
    end

    -- User chooses a private destination outside Lightroom's catalog/cache;
    -- do not write anything until the Save dialog has been confirmed.
    local destination = LrDialogs.runSavePanel {
        title = 'Save ProGrapher Smart Preview Research Evidence Locally',
        prompt = 'Save local evidence',
        requiredFileType = 'json',
        canCreateDirectories = true,
    }
    if not destination then return end
    local lowered = destination:lower():gsub('/', '\\')
    if lowered:find('.lrdata', 1, true)
       or lowered:find('.lrcat', 1, true)
       or not lowered:match('%.json$') then
        error('Choose a .json file OUTSIDE Lightroom catalog and preview folders.')
    end
    if LrFileUtils.exists(destination) then
        error('The file already exists. Choose a new filename (no overwrite).')
    end
    local payload = '{' ..
        '"schema":"prographer.lightroom.smart_preview_sdk_links.v1",' ..
        '"catalog_path":' .. q(catalog:getPath()) .. ',' ..
        '"records":[' .. table.concat(rows, ',') .. ']' ..
        '}'

    local file, err = io.open(destination, 'wb')
    if not file then error('Cannot create evidence file: ' .. tostring(err)) end
    file:write(payload)
    file:close()
    LrDialogs.message(
        'ProGrapher — Read-only Evidence Export',
        'Saved SDK paths for ' .. tostring(#rows) .. ' selected photos. ' ..
        'No photo or catalog was modified. Keep this JSON local and private.',
        'info'
    )
end

LrTasks.startAsyncTask(function()
    local ok, err = LrTasks.pcall(run)
    if not ok then
        LrDialogs.message('ProGrapher — Research STOP', tostring(err), 'critical')
    end
end)
