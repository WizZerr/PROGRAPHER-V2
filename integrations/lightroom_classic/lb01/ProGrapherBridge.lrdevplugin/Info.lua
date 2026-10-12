-- LB-01 / manually invoked research test only. NOT a commercial auto-worker.
return {
    LrSdkVersion = 6.0,
    LrSdkMinimumVersion = 6.0,
    LrToolkitIdentifier = 'com.prographer.lightroom.bridge.lb01.research',
    LrPluginName = 'ProGrapher Bridge — LB-01 Research Only',
    LrLibraryMenuItems = {
        { title = 'ProGrapher LB-01 Full Recipe Test (Research ONLY)', file = 'RunBridgeTest.lua' },
    },
    VERSION = { major = 0, minor = 4, revision = 0, build = 1 },
}
