// DecKoOS Weather: the weather where you are, from Open-Meteo (free, no account, no key), asked every 30 minutes
// while it's on screen: the temperature, what it's doing outside, and sunrise and sunset. The town is set in DecKoOS
// Hub (Appearance > Vibes > Desktop widgets), which writes its name and coordinates here.
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami
import org.deckos.vibes as Vibes

PlasmoidItem {
    id: weather

    Vibes.Look {
        id: look
        style: Plasmoid.configuration.style
        colorA: Plasmoid.configuration.colorA
        colorB: Plasmoid.configuration.colorB
    }

    readonly property string place: Plasmoid.configuration.place || ""
    readonly property real lat: Plasmoid.configuration.latitude
    readonly property real lon: Plasmoid.configuration.longitude
    readonly property bool fahrenheit: Plasmoid.configuration.fahrenheit === true
    property var now: null  // {temp, code, day, sunrise, sunset}
    property string problem: ""

    preferredRepresentation: fullRepresentation
    Layout.minimumWidth: 240
    Layout.preferredWidth: 300
    Layout.preferredHeight: 128
    Component.onCompleted: Plasmoid.backgroundHints = PlasmaCore.Types.NoBackground

    // WMO weather codes (Open-Meteo's) to words and an icon
    function describe(code, day) {
        const c = Number(code);
        if (c === 0) return ["Clear", day ? "weather-clear" : "weather-clear-night"];
        if (c <= 2) return ["Partly cloudy", day ? "weather-few-clouds" : "weather-few-clouds-night"];
        if (c === 3) return ["Cloudy", "weather-overcast"];
        if (c === 45 || c === 48) return ["Fog", "weather-fog"];
        if (c >= 51 && c <= 57) return ["Drizzle", "weather-showers-scattered"];
        if (c >= 61 && c <= 67) return ["Rain", "weather-showers"];
        if (c >= 71 && c <= 77) return ["Snow", "weather-snow"];
        if (c >= 80 && c <= 82) return ["Showers", "weather-showers"];
        if (c === 85 || c === 86) return ["Snow showers", "weather-snow-scattered"];
        if (c >= 95) return ["Thunderstorm", "weather-storm"];
        return ["", "weather-none-available"];
    }

    function refresh() {
        if (!place)
            return;
        const url = "https://api.open-meteo.com/v1/forecast?latitude=" + lat + "&longitude=" + lon
            + "&current=temperature_2m,weather_code,is_day&daily=sunrise,sunset&forecast_days=1&timezone=auto"
            + (fahrenheit ? "&temperature_unit=fahrenheit" : "");
        const req = new XMLHttpRequest();
        req.onreadystatechange = () => {
            if (req.readyState !== XMLHttpRequest.DONE)
                return;
            try {
                const d = JSON.parse(req.responseText);
                weather.now = { temp: Math.round(d.current.temperature_2m), code: d.current.weather_code,
                                day: d.current.is_day === 1, sunrise: d.daily.sunrise[0].slice(11, 16),
                                sunset: d.daily.sunset[0].slice(11, 16) };
                weather.problem = "";
            } catch (e) {
                weather.problem = "No weather right now (offline?)";
            }
        };
        req.open("GET", url);
        req.send();
    }
    Timer {
        interval: 30 * 60 * 1000
        running: weather.visible && weather.place !== ""
        repeat: true
        triggeredOnStart: true
        onTriggered: weather.refresh()
    }
    onPlaceChanged: refresh()

    Vibes.Plate { anchors.fill: parent; look: look; visible: look.plate }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 14
        visible: weather.place !== ""
        Kirigami.Icon {
            Layout.preferredWidth: 64
            Layout.preferredHeight: 64
            source: weather.now ? weather.describe(weather.now.code, weather.now.day)[1] : "weather-none-available"
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0
            Vibes.VibeText {
                look: look
                text: weather.now ? weather.now.temp + "°" : "–"
                font.pixelSize: 44
            }
            Vibes.VibeText {
                look: look
                soft: true
                Layout.fillWidth: true
                elide: Text.ElideRight
                text: weather.problem || (weather.now ? weather.describe(weather.now.code, true)[0] + " in " + weather.place
                                                      : weather.place)
                font.pixelSize: 14
            }
            Vibes.VibeText {
                look: look
                soft: true
                visible: !!weather.now
                text: weather.now ? "↑ " + weather.now.sunrise + "   ↓ " + weather.now.sunset : ""
                font.pixelSize: 13
            }
        }
    }
    Vibes.VibeText {
        look: look
        soft: true
        visible: weather.place === ""
        anchors.centerIn: parent
        width: parent.width - 32
        wrapMode: Text.Wrap
        horizontalAlignment: Text.AlignHCenter
        text: "Set your town in DecKoOS Hub: Appearance, Vibes, Desktop widgets"
        font.pixelSize: 14
    }
}
