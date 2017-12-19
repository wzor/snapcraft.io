import {formatAxis, formatXAxisTickLabels, formatYAxisTickLabels} from '../axis';
import debounce from '../../libs/debounce';
import {snapcraftGraphTooltip, positionTooltip} from '../tooltips';
import {COLORS} from '../config';

function showGraph(el) {
  formatAxis(el);
  el.style.opacity = 1;
}

export default function installsMetrics(days, installs) {
  const el = document.getElementById('installs_metrics');
  const installsMetricsOffset = {
    left: el.offsetLeft,
    top: el.offsetTop
  };

  const installsMetrics = bb.generate({
    bindto: '#installs_metrics',
    legend: {
      hide: true
    },
    padding: {
      top: 0,
      left: 72,
      bottom: 0,
      right: 112
    },
    tooltip: {
      contents: snapcraftGraphTooltip.bind(this, [COLORS.installs]),
      position: positionTooltip.bind(this, installsMetricsOffset, el)
    },
    transition: {
      duration: 0
    },
    point: {
      focus: false
    },
    axis: {
      x: {
        tick: {
          culling: false,
          outer: true,
          format: formatXAxisTickLabels
        }
      },
      y: {
        tick: {
          format: formatYAxisTickLabels
        }
      }
    },
    bar: {
      width: 4
    },
    resize: {
      auto: false
    },
    data: {
      colors: COLORS,
      type: 'bar',
      x: 'x',
      columns: [
        days,
        installs
      ]
    }
  });

  showGraph(el);

  // Extra events
  let elWidth = el.clientWidth;

  const resize = debounce(function () {
    if (el.clientWidth !== elWidth) {
      el.style.opacity = 0;
      debounce(function () {
        installsMetrics.resize();
        showGraph(el);
        elWidth = el.clientWidth;
      }, 100)();
    }
  }, 500);

  window.addEventListener('resize', resize);

  return installsMetrics;
}