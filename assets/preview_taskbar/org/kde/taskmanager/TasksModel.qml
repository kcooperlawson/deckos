import QtQuick
// Stand-in for TaskManager.TasksModel: canned apps (preview_taskbar.py fills it), no windows touched.
ListModel {
    enum SortMode { SortDisabled, SortManual }
    enum GroupMode { GroupDisabled, GroupApplications }
    property int sortMode
    property int groupMode
    property bool groupInline
    property bool separateLaunchers
    property bool launchInPlace
    property bool hideActivatedLaunchers
    property bool filterByVirtualDesktop
    property bool filterByActivity
    property bool filterByScreen
    property bool filterHidden
    property var virtualDesktop
    property string activity
    property rect screenGeometry
    property var launcherList: []
    Component.onCompleted: { for (const app of previewApps) append(app); }
    function makeModelIndex(row, child) { return { row: row, child: child === undefined ? -1 : child }; }
    function data(i, role) { return get(i.row).display; }
    function launcherPosition(url) { return launcherList.indexOf(url); }
    function requestActivate(i) {}
    function requestNewInstance(i) {}
    function requestClose(i) {}
    function requestToggleMinimized(i) {}
    function requestAddLauncher(url) {}
    function requestRemoveLauncher(url) {}
    function requestPublishDelegateGeometry(i, r, d) {}
    function syncLaunchers() {}
}
