-- User-facing research-only status action. Never creates jobs or changes photos.
local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrFileUtils = import 'LrFileUtils'
local LrPathUtils = import 'LrPathUtils'
local home = LrPathUtils.getStandardFilePath('home')
local root = LrPathUtils.child(LrPathUtils.child(home, 'Documents'), 'ProGrapher_Research_Private')
local work = LrPathUtils.child(LrPathUtils.child(LrPathUtils.child(root, 'SP_01_Catalog_Test'),
    'SP_01_AUTO_RETRY_01'), 'SP_01_AUTO_BRIDGE')
local result = LrPathUtils.child(work, 'result.txt')
local catalog = LrApplication.activeCatalog()
local expected = LrPathUtils.child(LrPathUtils.child(root, 'SP_01_Catalog_Test'),
    'SP_01_AUTO_RETRY_01')
expected = LrPathUtils.child(expected, 'SP_01_AUTO_RETRY_01.lrcat')
local function norm(p) return tostring(p or ''):gsub('/', '\\'):lower() end
local exact = catalog and norm(catalog:getPath()) == norm(expected)
local state = 'NO JOB PREPARED'
if LrFileUtils.exists(result) == 'file' then
    local contents = LrFileUtils.readFile(result)
    local parsed = contents and contents:match('^status=([a-z_]+)')
    state = parsed or 'NOT READABLE'
end
LrDialogs.message('ProGrapher SP-AUTO-01 — research status',
    'Authorized research catalog open: '..tostring(exact)..
    '\nJob state: '..state..
    '\nNo changes were made by this status command.', 'info')
