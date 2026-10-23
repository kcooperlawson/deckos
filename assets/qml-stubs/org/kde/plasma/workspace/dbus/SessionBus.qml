pragma Singleton
import QtQuick
QtObject { function asyncCall(msg, resolve, reject) { console.log("dbus", msg.member) } }
