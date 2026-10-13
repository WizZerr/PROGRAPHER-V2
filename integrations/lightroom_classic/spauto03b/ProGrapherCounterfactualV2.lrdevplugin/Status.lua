-- Read-only status of the one fresh SP03B research catalog.
local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrFileUtils = import 'LrFileUtils'
local LrPathUtils = import 'LrPathUtils'
local home = LrPathUtils.getStandardFilePath('home')
local root = LrPathUtils.child(LrPathUtils.child(home, 'Documents'), 'ProGrapher_Research_Private')
local folder = LrPathUtils.child(LrPathUtils.child(root, 'SP_01_Catalog_Test'), 'SP_01_AUTO_LEAK_02')
local expected = LrPathUtils.child(folder, 'SP_01_AUTO_LEAK_02.lrcat')
local result = LrPathUtils.child(LrPathUtils.child(folder, 'SP_03B_BRIDGE'), 'result.txt')
local function norm(p)
    return tostring(p or ''):gsub('/', '\\'):lower()
end
local catalog = LrApplication.activeCatalog()
local authorized = catalog and norm(catalog:getPath()) == norm(expected)
local state = 'NO JOB PREPARED'
if LrFileUtils.exists(result) == 'file' then
    local data = LrFileUtils.readFile(result)
    state = data and data:match('^status=([a-z_]+)') or 'NOT READABLE'
end
LrDialogs.message('ProGrapher SP-AUTO-03B — Crop-controlled research',
    'Authorized isolated research catalog: '..tostring(authorized)..
    '\nJob state: '..state..
    '\nRead only. Click OK before starting research.', 'info')
