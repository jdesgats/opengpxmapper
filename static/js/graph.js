define([
  "lib/aristochart",
  "lib/underscore",
],
function(Aristochart, _) {
  
  // different x scales for time based graphs (in minutes)
  var timeScales = _.map([ 1, 5, 10, 15, 20, 30, 60, 90, 120, 180, 240 ], function(x) { return x * 60000 });
  var yScales = [ 1, 5, 10, 15, 20, 50, 100, 200, 500, 1000 ];
  
  var findStep = function(value, steps, maxSteps) {
    return _.find(steps, function(x) { return value / x <= maxSteps });
  }
  
  var timeGraph = function(target, data, yselector, title) {
    var timeRange = [ 0, Date.parse(_.last(data).timestamp) - Date.parse(data[0].timestamp) ];
    var ydata = _.map(data, yselector)
    var yRange = [ _.min(ydata), _.max(ydata) ]
    var yStep = findStep(yRange[1] - yRange[0], yScales, 3);
    var yActualRange = [ Math.floor(yRange[0] / yStep) * yStep, Math.ceil(yRange[1] / yStep) * yStep ]
    
    var mouseMoved = function(evt) {
      var rect = this.getBoundingClientRect();
      var i = Math.floor(((evt.clientX - rect.left) * data.length) / this.width);
      // TODO: initCustomEvent polyfill
      var evt = new CustomEvent("pointselected", { bubbles: false, cancelable: true, detail: data[i] });
      this.dispatchEvent(evt);
    }

    var chart = new Aristochart(target, {
      width: 300,
      height: 75,
      margin: 0,
      padding: 0,
      title: { x: title, }, // FIXME: title is really a hack currently
      data: { x: timeRange, y: ydata, },
      axis: {
        x: { steps: timeRange[1] / findStep(timeRange[1], timeScales, 5) },
        y: {
          min: yActualRange[0],
          max: yActualRange[1],
          steps: (yActualRange[1] - yActualRange[0]) / yStep,
        },
      },
      label: {
        x: {
          format: function(n) {
            if (n === 0) return "";
            var min = Math.round((n%3600000) / 60000);
            return (Math.floor(n/3600000) + ":" + (min < 10 ? ("0" + min) : min.toString()));
          },
        },
        y: { format: function(n, i) {
          return n == yActualRange[0] || n == yActualRange[1] ? "" : n.toString();
        } }
      },
      style: {
        default: {
          point: { visible: false, },
          line: {
            width: 1,
            fill: "#181C26",
            stroke: "#515E80",
          },
          label: {
            x: { offsetY: -8, fontSize: 8, color: "#ccc" },
            y: { offsetX: -14, offsetY: 5, fontSize: 8, color: "#ccc" },
          },
          tick: {
            align: "inside",
            minor: 4,
            major: 4,
          },
          title: {
            color: "#ccc",
            font: "Helvetica",
            fontSize: "9",
            fontStyle: "",
            x: { offsetX: 0, offsetY: -65, }
          }
        }
      }
    });
    chart.canvas.addEventListener("mousemove", mouseMoved);
    return chart;
  }
  
  return {
    speedGraph: function(target, data) {
      return timeGraph(target, data, function(x) { return x.speed * 3.6; }, "Vitesse (km/h)");
    },
    altGraph: function(target, data) {
      return timeGraph(target, data, function(x) { return x.ele; }, "Altitude (m)");
    },
  };
});