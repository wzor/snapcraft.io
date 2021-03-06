const LATEST = 'latest';

function setTrack(arch, track, packageName, channelMap) {
  ['stable', 'candidate', 'beta', 'edge'].forEach((risk, i, risks) => {
    const channelEl = document.getElementById(`js-channel-map-${risk}`);

    // channel names in tracks other then latest are prefixed with track name
    const channelName = track === LATEST ? risk : `${track}/${risk}`;

    channelEl.querySelector('.js-channel-name').innerHTML = channelName;
    let channelData = channelMap[channelName];

    // update install instructions
    let command = `sudo snap install ${packageName}`;

    if (track === LATEST) {
      if (risk !== 'stable') {
        command += ` --${risk}`;
      }
    } else {
      command += ` --channel=${track}/${risk}`;
    }

    channelEl.querySelector('input').value = command;

    const versionEl = channelEl.querySelector('.p-form-help-text');
    channelEl.classList.remove('p-channel-map__row--closed');

    // show version
    if (channelData) {
      versionEl.innerHTML = `Version: ${channelData.version}`;
    } else {
      let fallbackRisk;
      for (let j = 0; j < i; j++) {
        const channelName = track === LATEST ? risks[j] : `${track}/${risks[j]}`;
        if (channelMap[channelName]) {
          fallbackRisk = risks[j];
        }
      }

      if (fallbackRisk) {
        versionEl.innerHTML = `No release in ${risk} channel, using ${fallbackRisk} release.`;
      } else {
        versionEl.innerHTML = `No release in ${risk} channel.`;
        channelEl.classList.add('p-channel-map__row--closed');
      }
    }
  });
}


function getArchTrackChannels(arch, track, channelMapData) {
  const channels = channelMapData[arch][track];
  const archTrackChannels = {};

  channels.forEach(channel => {
    archTrackChannels[channel.channel] = channel;
  });

  return archTrackChannels;
}

function setArchitecture(arch, packageName, channelMapData) {
  if (!arch) {
    return;
  }

  const tracks = Object.keys(channelMapData[arch]);

  // sort tracks alphabetically with 'latest' always first
  tracks.sort((a, b) => {
    if (a === LATEST) {
      return -1;
    }
    if (b === LATEST) {
      return 1;
    }
    return a <= b ? -1 : 1;
  });

  // by default take first track (which should be 'latest')
  const track = tracks[0];

  if (!track) {
    return;
  }

  // update tracks select
  const trackSelect = document.getElementById("js-channel-map-track-select");
  trackSelect.innerHTML = tracks.map(track => `<option value="${track}">${track}</option>`).join('');
  trackSelect.value = track;

  // hide tracks if there is only one
  if (tracks.length === 1) {
    trackSelect.closest('.js-channel-map-track-field').style.display = 'none';
  } else {
    trackSelect.closest('.js-channel-map-track-field').style.display = '';
  }

  const channelMap = getArchTrackChannels(arch, track, channelMapData);
  setTrack(arch, track, packageName, channelMap);
}

export default function initChannelMap(el, packageName, channelMapData) {
  const channelMapEl = document.querySelector(el);
  const channelOverlayEl = document.querySelector('.p-channel-map-overlay');
  let closeTimeout;

  // init open/hide buttons
  const openChannelMap = () => {
    // clear hiding animation if it's still running
    clearTimeout(closeTimeout);
    // make sure overlay is displayed before CSS transitions are triggered
    channelOverlayEl.style.display = 'block';
    setTimeout(() => channelMapEl.classList.remove('is-closed'), 10);

    window.addEventListener('keyup', hideOnEscape);
    document.addEventListener('click', hideOnClick);
  };

  const hideChannelMap = () => {
    channelMapEl.classList.add('is-closed');
    // hide overlay after CSS transition is finished
    closeTimeout = setTimeout(() => channelOverlayEl.style.display = 'none', 500);

    window.removeEventListener('keyup', hideOnEscape);
    document.removeEventListener('click', hideOnClick);
  };

  const hideOnEscape = (event) => {
    if (event.key === "Escape" && !channelMapEl.classList.contains('is-closed')) {
      hideChannelMap();
    }
  };

  const hideOnClick = (event) => {
    // when channel map is not closed and clicking outside of it, close it
    if (!channelMapEl.classList.contains('is-closed') &&
        !event.target.closest(el)) {
      hideChannelMap();
    }
  };

  // show/hide when clicking on buttons
  document.querySelector('.js-open-channel-map').addEventListener('click', openChannelMap);
  document.querySelector('.js-hide-channel-map').addEventListener('click', hideChannelMap);

  // get architectures from data
  const architectures = Object.keys(channelMapData);

  // initialize arch and track selects
  const archSelect = document.getElementById("js-channel-map-architecture-select");
  const trackSelect = document.getElementById("js-channel-map-track-select");

  archSelect.innerHTML = architectures.map(arch => `<option value="${arch}">${arch}</option>`).join('');

  archSelect.addEventListener('change', ()=> {
    setArchitecture(archSelect.value, packageName, channelMapData);
  });

  trackSelect.addEventListener('change', ()=> {
    const channels = getArchTrackChannels(archSelect.value, trackSelect.value, channelMapData);
    setTrack(archSelect.value, trackSelect.value, packageName, channels);
  });

  const arch = channelMapData['amd64'] ? 'amd64' : architectures[0];
  archSelect.value = arch;
  setArchitecture(arch, packageName, channelMapData);
}
