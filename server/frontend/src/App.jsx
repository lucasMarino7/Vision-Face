import { useEffect, useRef, useState } from 'react';
import {
  Activity, AlertTriangle, Camera, Check, ChevronDown, CircleHelp, Cpu, Eye,
  Fingerprint, LayoutDashboard, LoaderCircle, Pencil, Plus, Radio, Search,
  ShieldAlert, Trash2, UserRound, Users, Wifi, WifiOff, X,
} from 'lucide-react';

const API = '/api';
const WS_DEFAULT = import.meta.env.VITE_RASPBERRY_WS_URL || '';

async function request(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.message || `Falha na requisição (${response.status})`);
  }
  return response.status === 204 ? null : response.json();
}

function ageFromDate(date) {
  if (!date) return null;
  const birth = new Date(`${date}T00:00:00`);
  if (Number.isNaN(birth.getTime())) return null;
  const today = new Date();
  return today.getFullYear() - birth.getFullYear() -
    (today < new Date(today.getFullYear(), birth.getMonth(), birth.getDate()) ? 1 : 0);
}

// datas no formato brasileiro (dd/mm/aaaa) na interface; a API continua usando ISO (aaaa-mm-dd)
function maskDate(value) {
  const digits = value.replace(/\D/g, '').slice(0, 8);
  return [digits.slice(0, 2), digits.slice(2, 4), digits.slice(4)].filter(Boolean).join('/');
}

function isoToBr(iso) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '');
  return match ? `${match[3]}/${match[2]}/${match[1]}` : '';
}

function brToIso(br) {
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(br || '');
  if (!match) return null;
  const [, day, month, year] = match;
  const parsed = new Date(Number(year), Number(month) - 1, Number(day));
  const valid = parsed.getFullYear() === Number(year) && parsed.getMonth() === Number(month) - 1 && parsed.getDate() === Number(day);
  return valid ? `${year}-${month}-${day}` : null;
}

function formatDate(date) {
  if (!date) return 'Não informada';
  const parsed = new Date(`${date}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? date : parsed.toLocaleDateString('pt-BR');
}

function normalizeDetection(message) {
  const data = message.person || message.data || message;
  const box = message.box || message.bbox || message.bounding_box || data.box || data.bbox;
  return {
    id: `${Date.now()}-${Math.random()}`,
    recognized: message.recognized ?? Boolean(message.person),
    person_id: data.id ?? data.person_id ?? null,
    model: message.model,
    name: message.recognized === false || !message.person ? null : (data.name || 'Pessoa identificada'),
    date_birth: data.date_birth,
    age: data.age ?? ageFromDate(data.date_birth),
    wanted: Boolean(data.wanted),
    reason: data.reason,
    embedding: message.embedding ?? data.embedding,
    box: box && {
      x: Number(box.x ?? box.left ?? 0),
      y: Number(box.y ?? box.top ?? 0),
      width: Number(box.width ?? box.w ?? 0),
      height: Number(box.height ?? box.h ?? 0),
    },
    timestamp: new Date(),
  };
}

function syncLabel(sync) {
  if (sync.syncing) return 'Sincronizando…';
  if (sync.next_sync_at == null) return 'Sincronização pendente';
  const remaining = Math.max(0, Math.round(sync.next_sync_in - (Date.now() - sync.receivedAt) / 1000));
  const at = new Date(sync.next_sync_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  return `${sync.backend_online === false ? 'Backend offline · ' : ''}Próxima sync: ${at} (em ${remaining}s)`;
}

function IconButton({ label, onClick, children, danger = false }) {
  return <button className={`icon-button${danger ? ' danger' : ''}`} type="button" title={label} aria-label={label} onClick={onClick}>{children}</button>;
}

function Modal({ title, onClose, children, wide = false }) {
  useEffect(() => {
    const onKeyDown = (event) => event.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);
  return <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
    <section className={`modal${wide ? ' modal-wide' : ''}`} role="dialog" aria-modal="true" aria-label={title}>
      <header className="modal-header"><h2>{title}</h2><IconButton label="Fechar" onClick={onClose}><X size={18} /></IconButton></header>
      {children}
    </section>
  </div>;
}

function App() {
  const [page, setPage] = useState('live');
  const [people, setPeople] = useState([]);
  const [embeddings, setEmbeddings] = useState([]);
  const [selectedPersonId, setSelectedPersonId] = useState(null);
  const [search, setSearch] = useState('');
  const [embeddingSearch, setEmbeddingSearch] = useState('');
  const [loadingPeople, setLoadingPeople] = useState(true);
  const [loadingEmbeddings, setLoadingEmbeddings] = useState(false);
  const [apiError, setApiError] = useState('');
  const [toast, setToast] = useState('');
  const [personModal, setPersonModal] = useState(null);
  const [embeddingModal, setEmbeddingModal] = useState(null);
  const [liveFaces, setLiveFaces] = useState([]);
  const [sync, setSync] = useState(null);
  const [raspberryUrl, setRaspberryUrl] = useState(() => localStorage.getItem('raspberryWsUrl') || WS_DEFAULT);
  const [activeRaspberryUrl, setActiveRaspberryUrl] = useState('');
  const [connectionEnabled, setConnectionEnabled] = useState(false);
  const [raspberryOnline, setRaspberryOnline] = useState(false);
  const [cameraOnline, setCameraOnline] = useState(false);
  const [socketError, setSocketError] = useState('');
  const [fps, setFps] = useState(null);
  const [assignModal, setAssignModal] = useState(null);
  const [filter, setFilter] = useState('all');
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const peerRef = useRef(null);
  const socketRef = useRef(null);
  const streamRef = useRef(null);
  const facesRef = useRef({ faces: [], at: 0 });

  const selectedPerson = people.find((person) => person.id === selectedPersonId);
  const filteredPeople = people.filter((person) => {
    const matchesSearch = `${person.name} ${person.id}`.toLowerCase().includes(search.toLowerCase());
    return matchesSearch && (filter === 'all' || (filter === 'wanted' ? person.wanted : !person.wanted));
  });
  const filteredEmbeddings = embeddings.map((embedding) => ({
    ...embedding,
    person: people.find((person) => person.id === embedding.person_id),
  })).filter((embedding) => {
    const personName = embedding.person?.name ?? '';
    const query = embeddingSearch.toLowerCase();
    return `${embedding.id} ${embedding.person_id} ${personName} ${embedding.model} ${embedding.angle}`.toLowerCase().includes(query);
  });

  async function loadPeople() {
    setLoadingPeople(true);
    try {
      const records = await request('/person/');
      setPeople(records);
      setApiError('');
      setSelectedPersonId((current) => current && records.some((person) => person.id === current) ? current : records[0]?.id ?? null);
    } catch (error) {
      setApiError(error.message);
    } finally {
      setLoadingPeople(false);
    }
  }

  async function loadEmbeddings() {
    setLoadingEmbeddings(true);
    try {
      setEmbeddings(await request('/embedding/'));
      setApiError('');
    } catch (error) {
      setApiError(error.message);
    } finally {
      setLoadingEmbeddings(false);
    }
  }

  useEffect(() => { loadPeople(); }, []);
  useEffect(() => {
    if (page === 'embeddings') loadEmbeddings();
  }, [page]);

  // rostos em tempo real: some da lista quando a Raspberry para de enviar frames
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (Date.now() - facesRef.current.at > 1500) {
        facesRef.current = { faces: [], at: 0 };
        setLiveFaces((current) => (current.length ? [] : current));
      }
    }, 500);
    return () => window.clearInterval(timer);
  }, []);

  // contagem regressiva local da próxima sincronização
  const [, setTick] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => setTick((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    let animationFrame;
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return undefined;
    const draw = () => {
      const context = canvas.getContext('2d');
      const width = video.videoWidth;
      const height = video.videoHeight;
      if (!width || !height) {
        // sem vídeo (desconectado): limpa qualquer box que tenha ficado no canvas
        context.clearRect(0, 0, canvas.width, canvas.height);
      } else {
        if (canvas.width !== width || canvas.height !== height) {
          canvas.width = width;
          canvas.height = height;
        }
        context.clearRect(0, 0, width, height);
        const live = Date.now() - facesRef.current.at < 1500 ? facesRef.current.faces : [];
        live.forEach((detection) => {
          if (!detection.box) return;
          const { x, y, width: boxWidth, height: boxHeight } = detection.box;
          const scaleX = x <= 1 && boxWidth <= 1 ? width : 1;
          const scaleY = y <= 1 && boxHeight <= 1 ? height : 1;
          const left = x * scaleX;
          const top = y * scaleY;
          const rectWidth = boxWidth * scaleX;
          const rectHeight = boxHeight * scaleY;
          context.strokeStyle = detection.wanted ? '#f26b52' : '#b9ed63';
          context.lineWidth = Math.max(2, width / 500);
          context.strokeRect(left, top, rectWidth, rectHeight);
          const label = detection.name || 'Não reconhecida';
          context.font = `600 ${Math.max(14, width / 75)}px sans-serif`;
          const labelWidth = context.measureText(label).width + 18;
          context.fillStyle = detection.wanted ? '#f26b52' : '#b9ed63';
          context.fillRect(left, Math.max(0, top - 32), labelWidth, 30);
          context.fillStyle = '#172019';
          context.fillText(label, left + 9, Math.max(0, top - 11));
        });
      }
      animationFrame = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(animationFrame);
  }, [page]);

  // O <video> é desmontado ao sair da página ao vivo; reanexa o stream ao voltar.
  useEffect(() => {
    const video = videoRef.current;
    if (page === 'live' && video && streamRef.current && video.srcObject !== streamRef.current) {
      video.srcObject = streamRef.current;
      video.play().catch(() => {});
    }
  }, [page]);

  useEffect(() => {
    if (!connectionEnabled || !activeRaspberryUrl.trim()) {
      setRaspberryOnline(false);
      setCameraOnline(false);
      setFps(null);
      setSync(null);
      setLiveFaces([]);
      facesRef.current = { faces: [], at: 0 };
      return undefined;
    }
    let retryTimer;
    let disposed = false;
    let peer;
    const connect = () => {
      if (disposed) return;
      let socket;
      try {
        socket = new WebSocket(activeRaspberryUrl.trim());
      } catch {
        setSocketError('Endereço WebSocket inválido.');
        return;
      }
      socketRef.current = socket;
      socket.onopen = () => {
        setRaspberryOnline(true);
        setSocketError('');
      };
      socket.onmessage = async (event) => {
        let message;
        try { message = JSON.parse(event.data); } catch { return; }
        if (message.type === 'faces') {
          const faces = Array.isArray(message.faces) ? message.faces.map(normalizeDetection) : [];
          facesRef.current = { faces, at: Date.now() };
          setLiveFaces(faces);
        } else if (message.type === 'status') {
          setCameraOnline(Boolean(message.camera_online));
          if (typeof message.fps === 'number') setFps(message.fps);
          if (message.sync) setSync({ ...message.sync, receivedAt: Date.now() });
          if (!message.camera_online) setFps(null);
        } else if (message.type === 'offer' && message.sdp) {
          peer = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] });
          peerRef.current = peer;
          peer.ontrack = (trackEvent) => {
            streamRef.current = trackEvent.streams[0];
            if (videoRef.current) videoRef.current.srcObject = streamRef.current;
            setCameraOnline(true);
          };
          peer.onconnectionstatechange = () => {
            setCameraOnline(peer.connectionState === 'connected');
          };
          peer.onicecandidate = ({ candidate }) => {
            if (candidate && socket.readyState === WebSocket.OPEN) {
              socket.send(JSON.stringify({ type: 'ice-candidate', candidate }));
            }
          };
          try {
            await peer.setRemoteDescription(new RTCSessionDescription(message.sdp));
            await peer.setLocalDescription(await peer.createAnswer());
            socket.send(JSON.stringify({ type: 'answer', sdp: peer.localDescription }));
          } catch (error) {
            setSocketError(`Negociação de vídeo falhou: ${error.message}`);
          }
        } else if (message.type === 'ice-candidate' && message.candidate && peer) {
          await peer.addIceCandidate(new RTCIceCandidate(message.candidate)).catch(() => {});
        }
      };
      socket.onerror = () => setSocketError('Não foi possível conectar ao WebSocket da Raspberry.');
      socket.onclose = () => {
        setRaspberryOnline(false);
        setCameraOnline(false);
        if (videoRef.current) videoRef.current.srcObject = null;
        peer?.close();
        streamRef.current = null;
        if (!disposed) retryTimer = window.setTimeout(connect, 3000);
      };
    };
    connect();
    return () => {
      disposed = true;
      window.clearTimeout(retryTimer);
      socketRef.current?.close();
      peer?.close();
      peerRef.current = null;
      socketRef.current = null;
      streamRef.current = null;
      if (videoRef.current) videoRef.current.srcObject = null;
    };
  }, [connectionEnabled, activeRaspberryUrl]);

  function configureRaspberry(event) {
    event.preventDefault();
    localStorage.setItem('raspberryWsUrl', raspberryUrl.trim());
    setConnectionEnabled(false);
    setActiveRaspberryUrl(raspberryUrl.trim());
    window.setTimeout(() => setConnectionEnabled(true), 0);
  }

  async function savePerson(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const dateBirth = brToIso(form.get('date_birth'));
    if (!dateBirth) { setToast('Informe uma data de nascimento válida no formato dd/mm/aaaa.'); return; }
    const payload = {
      name: form.get('name').trim(),
      date_birth: dateBirth,
      wanted: form.get('wanted') === 'on',
      reason: form.get('reason').trim() || null,
    };
    try {
      const existing = personModal.person;
      const saved = await request(existing ? `/person/${existing.id}` : '/person/', {
        method: existing ? 'PUT' : 'POST', body: JSON.stringify(payload),
      });
      const detection = personModal.detection;
      setPersonModal(null);
      if (!existing && detection) {
        await attachEmbedding(saved.id, detection, form.get('angle') || 'frontal');
        return;
      }
      setToast(existing ? 'Cadastro atualizado.' : 'Pessoa cadastrada.');
      await loadPeople();
    } catch (error) { setToast(error.message); }
  }

  async function attachEmbedding(personId, detection, angle) {
    try {
      await request(`/embedding/${personId}/embeddings`, {
        method: 'POST',
        body: JSON.stringify({ embedding: detection.embedding, model: (detection.model || 'buffalo_l').slice(0, 20), angle: angle.trim().slice(0, 20) || 'frontal' }),
      });
      setAssignModal(null);
      setToast('Embedding atrelada à pessoa.');
      await loadPeople();
    } catch (error) { setToast(error.message); }
  }

  async function deletePerson(person) {
    if (!window.confirm(`Excluir ${person.name} e todas as embeddings associadas?`)) return;
    try {
      await request(`/person/${person.id}`, { method: 'DELETE' });
      setToast('Pessoa removida.');
      await loadPeople();
    } catch (error) { setToast(error.message); }
  }

  async function saveEmbedding(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    let vector;
    try {
      vector = form.get('embedding').split(/[\s,;]+/).filter(Boolean).map(Number);
      if (vector.length !== 512 || vector.some((value) => !Number.isFinite(value))) {
        throw new Error('A embedding deve conter exatamente 512 números válidos.');
      }
    } catch (error) { setToast(error.message); return; }
    const payload = { embedding: vector, model: form.get('model').trim(), angle: form.get('angle').trim() };
    try {
      const { person, embedding } = embeddingModal;
      await request(embedding ? `/embedding/${person.id}/embeddings/${embedding.id}` : `/embedding/${person.id}/embeddings`, {
        method: embedding ? 'PUT' : 'POST', body: JSON.stringify(payload),
      });
      setEmbeddingModal(null);
      setToast(embedding ? 'Embedding atualizada.' : 'Embedding adicionada.');
      await loadPeople();
      if (page === 'embeddings') await loadEmbeddings();
    } catch (error) { setToast(error.message); }
  }

  async function deleteEmbedding(person, embedding) {
    if (!window.confirm(`Remover a embedding ${embedding.id}?`)) return;
    try {
      await request(`/embedding/${person.id}/embeddings/${embedding.id}`, { method: 'DELETE' });
      setToast('Embedding removida.');
      await loadPeople();
      if (page === 'embeddings') await loadEmbeddings();
    } catch (error) { setToast(error.message); }
  }

  useEffect(() => {
    if (!toast) return undefined;
    const timer = window.setTimeout(() => setToast(''), 3200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="#inicio" onClick={() => setPage('live')}><span className="brand-mark"><Eye size={19} /></span><span>VISION<span className="brand-light">FACE</span><small>FIELD INTELLIGENCE</small></span></a>
      <div className="side-label">OPERAÇÃO</div>
      <nav className="navigation" aria-label="Navegação principal">
        <button className={page === 'live' ? 'nav-item active' : 'nav-item'} onClick={() => setPage('live')}><LayoutDashboard size={18} /> Visão ao vivo <span className="nav-live" /></button>
        <button className={page === 'people' ? 'nav-item active' : 'nav-item'} onClick={() => setPage('people')}><Users size={18} /> Pessoas cadastradas</button>
        <button className={page === 'embeddings' ? 'nav-item active' : 'nav-item'} onClick={() => setPage('embeddings')}><Fingerprint size={18} /> Embeddings</button>
      </nav>
      <div className="sidebar-spacer" />
      <div className="sidebar-foot"><span>VISION FACE</span><span>MONITOR v1.0</span></div>
    </aside>

    <main className="main-content">
      <header className="topbar">
        <div><div className="breadcrumbs">VISION FACE <span>/</span> {page === 'live' ? 'MONITORAMENTO' : page === 'people' ? 'CADASTROS' : 'BIOMETRIA'}</div><h1>{page === 'live' ? 'Monitoramento ao vivo' : page === 'people' ? 'Pessoas cadastradas' : 'Embeddings faciais'}</h1></div>
        <div className="topbar-meta"><span className={`connection-pill ${raspberryOnline ? 'connected' : ''}`}><span className="tiny-dot" />{raspberryOnline ? 'Dispositivo conectado' : 'Sem dispositivo'}</span>{sync && <span className={`connection-pill ${sync.syncing ? 'connected' : ''}`}><span className="tiny-dot" />{syncLabel(sync)}</span>}</div>
      </header>

      {page === 'live' ? <section className="live-page">
        <form className="connection-bar" onSubmit={configureRaspberry}>
          <div className="connection-icon"><Radio size={18} /></div>
          <label htmlFor="raspberry-url"><span>ENDPOINT DA RASPBERRY</span><input id="raspberry-url" value={raspberryUrl} onChange={(event) => setRaspberryUrl(event.target.value)} placeholder={WS_DEFAULT || 'ws://192.168.1.20:8765'} /></label>
          {connectionEnabled
            ? <button key="disconnect" className="button button-quiet" type="button" onClick={() => setConnectionEnabled(false)}><WifiOff size={16} /> Desconectar</button>
            : <button key="connect" className="button button-dark" type="submit"><Wifi size={16} /> Conectar</button>}
          {socketError && <span className="connection-error"><AlertTriangle size={14} />{socketError}</span>}
        </form>
        <div className="live-grid">
          <section className="camera-panel">
            <header className="panel-header"><div><span className="eyebrow">CÂMERA RASP</span><h2>Stream de reconhecimento</h2></div><span className={`live-indicator ${cameraOnline ? 'is-live' : ''}`}><span />{cameraOnline ? 'AO VIVO' : 'SEM SINAL'}</span></header>
            <div className={`video-stage ${cameraOnline ? 'has-video' : ''}`}>
              <video ref={videoRef} autoPlay playsInline muted />
              <canvas ref={canvasRef} />
              {!cameraOnline && <div className="offline-state"><div className="offline-icon"><Camera size={27} /><span><WifiOff size={15} /></span></div><strong>Raspberry desconectada</strong><p>O vídeo aparecerá aqui quando a câmera estiver transmitindo.</p></div>}
              {cameraOnline && <div className="video-corner-label"><span className="tiny-dot online" /> STREAM WEBRTC{fps != null && ` · ${fps.toFixed(1)} FPS`}</div>}
              <div className="video-timestamp"><Activity size={13} /> {new Date().toLocaleTimeString('pt-BR')}</div>
            </div>
            <footer className="camera-footer"><span><span className={`tiny-dot ${cameraOnline ? 'online' : ''}`} />{cameraOnline ? 'Stream ativo via WebRTC' : 'Aguardando stream de vídeo'}</span><span><Activity size={14} /> {fps != null ? `${fps.toFixed(1)} FPS (câmera)` : '— FPS'}</span><span><Cpu size={14} /> Detecção facial habilitada</span></footer>
          </section>
          <section className="detections-panel">
            <header className="panel-header detections-header"><div><span className="eyebrow">TEMPO REAL</span><h2>Rostos identificados</h2></div><span className="count-badge">{liveFaces.length}</span></header>
            <div className="detections-list">
              {liveFaces.length === 0 ? <div className="empty-detections"><div className="empty-icon"><Fingerprint size={22} /></div><strong>Nenhum rosto na câmera</strong><p>Os rostos visíveis agora na câmera serão listados aqui.</p></div> : liveFaces.map((detection, index) => <article className={`detection-item ${detection.wanted ? 'wanted-item' : ''}`} key={index}>
                <div className="detection-avatar">{detection.name ? <UserRound size={17} /> : <CircleHelp size={18} />}</div>
                <div className="detection-main"><strong>{detection.name || 'Pessoa não reconhecida'}</strong><span>{detection.age != null ? `${detection.age} anos` : 'Idade não informada'}</span>{detection.date_birth && <span>Nascimento: {formatDate(detection.date_birth)}</span>}{detection.wanted && <span className="wanted-tag"><ShieldAlert size={12} /> PROCURADO</span>}{detection.wanted && detection.reason && <p className="wanted-reason">{detection.reason}</p>}{!detection.recognized && Array.isArray(detection.embedding) && <button className="button button-accent" type="button" onClick={() => setAssignModal({ detection })}><Plus size={14} /> Adicionar</button>}{Array.isArray(detection.embedding) && <details className="detection-embedding"><summary>Embedding facial ({detection.embedding.length})</summary><code>{JSON.stringify(detection.embedding)}</code></details>}</div>
                <time>{detection.timestamp.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</time>
              </article>) }
            </div>
            </section>
        </div>
        </section> : page === 'people' ? <section className="people-page">
        <div className="people-toolbar"><div className="people-summary"><span className="summary-number">{people.length.toString().padStart(2, '0')}</span><span>REGISTROS NO SISTEMA</span></div><div className="people-actions"><label className="search-field"><Search size={16} /><input placeholder="Buscar por nome ou ID" value={search} onChange={(event) => setSearch(event.target.value)} /></label><div className="filter-wrap"><select value={filter} onChange={(event) => setFilter(event.target.value)} aria-label="Filtrar pessoas"><option value="all">Todos os registros</option><option value="wanted">Procurados</option><option value="regular">Demais pessoas</option></select><ChevronDown size={14} /></div><button className="button button-accent" onClick={() => setPersonModal({ person: null })}><Plus size={17} /> Nova pessoa</button></div></div>
        {apiError && <div className="api-error"><AlertTriangle size={17} /><span>Não foi possível carregar a API: {apiError}</span><button className="text-button" onClick={loadPeople}>Tentar novamente</button></div>}
        <div className="registry-layout">
          <section className="registry-table-wrap"><table className="registry-table"><thead><tr><th>PESSOA</th><th>NASCIMENTO</th><th>IDADE</th><th>STATUS</th><th>EMBEDDINGS</th><th></th></tr></thead><tbody>
            {loadingPeople ? <tr><td colSpan="6" className="table-state"><LoaderCircle className="spin" size={20} /> Carregando cadastros</td></tr> : filteredPeople.length === 0 ? <tr><td colSpan="6" className="table-state">Nenhuma pessoa encontrada.</td></tr> : filteredPeople.map((person) => <tr className={person.id === selectedPersonId ? 'selected-row' : ''} key={person.id} onClick={() => setSelectedPersonId(person.id)}>
              <td><div className="person-cell"><span className="person-avatar"><UserRound size={17} /></span><span><strong>{person.name}</strong><small>ID {String(person.id).padStart(4, '0')}</small></span></div></td><td>{formatDate(person.date_birth)}</td><td>{ageFromDate(person.date_birth) ?? '—'}</td><td><span className={`person-status ${person.wanted ? 'wanted' : 'clear'}`}><span />{person.wanted ? 'Procurado' : 'Regular'}</span></td><td><span className="embedding-count"><Fingerprint size={14} />{person.embeddings?.length ?? 0}</span></td><td><div className="row-actions" onClick={(event) => event.stopPropagation()}><IconButton label="Editar pessoa" onClick={() => setPersonModal({ person })}><Pencil size={15} /></IconButton><IconButton label="Excluir pessoa" danger onClick={() => deletePerson(person)}><Trash2 size={15} /></IconButton></div></td>
            </tr>) }
          </tbody></table></section>
          <aside className="detail-panel">
            {selectedPerson ? <>
              <div className="detail-heading"><span className="eyebrow">FICHA DE CADASTRO</span><div className="detail-person"><span className="detail-avatar"><UserRound size={22} /></span><div><h2>{selectedPerson.name}</h2><span>Registro #{String(selectedPerson.id).padStart(4, '0')}</span></div><IconButton label="Editar pessoa" onClick={() => setPersonModal({ person: selectedPerson })}><Pencil size={16} /></IconButton></div></div>
              <div className="detail-fields"><div><span>DATA DE NASCIMENTO</span><strong>{formatDate(selectedPerson.date_birth)}</strong></div><div><span>IDADE</span><strong>{ageFromDate(selectedPerson.date_birth) ?? '—'} anos</strong></div><div><span>STATUS JUDICIAL</span><strong className={selectedPerson.wanted ? 'text-danger' : ''}>{selectedPerson.wanted ? 'Procurado pela justiça' : 'Sem alerta registrado'}</strong></div>{selectedPerson.wanted && selectedPerson.reason && <div className="reason-field"><span>MOTIVO INFORMADO</span><strong>{selectedPerson.reason}</strong></div>}</div>
              <div className="embedding-section"><header><div><span className="eyebrow">DADOS BIOMÉTRICOS</span><h3>Embeddings faciais <span>{selectedPerson.embeddings?.length ?? 0}</span></h3></div><IconButton label="Adicionar embedding" onClick={() => setEmbeddingModal({ person: selectedPerson, embedding: null })}><Plus size={18} /></IconButton></header>
                {!selectedPerson.embeddings?.length ? <div className="no-embeddings"><Fingerprint size={18} /><span>Nenhuma embedding cadastrada.</span></div> : <div className="embedding-list">{selectedPerson.embeddings.map((embedding) => <article className="embedding-row" key={embedding.id}><span className="embedding-icon"><Fingerprint size={16} /></span><div><strong>Embedding #{embedding.id}</strong><small>{embedding.model} · {embedding.angle} · {embedding.dimension} dimensões</small></div><IconButton label="Editar embedding" onClick={() => setEmbeddingModal({ person: selectedPerson, embedding })}><Pencil size={14} /></IconButton><IconButton label="Remover embedding" danger onClick={() => deleteEmbedding(selectedPerson, embedding)}><Trash2 size={14} /></IconButton></article>)}</div>}
              </div>
            </> : <div className="detail-empty"><Users size={24} /><strong>Selecione uma pessoa</strong><span>Os detalhes do cadastro serão exibidos aqui.</span></div>}
          </aside>
        </div>
      </section> : <section className="embeddings-page">
        <div className="embeddings-toolbar"><div className="people-summary"><span className="summary-number">{embeddings.length.toString().padStart(2, '0')}</span><span>VETORES CADASTRADOS</span></div><label className="search-field"><Search size={16} /><input placeholder="Buscar por pessoa, modelo ou ID" value={embeddingSearch} onChange={(event) => setEmbeddingSearch(event.target.value)} /></label></div>
        {apiError && <div className="api-error"><AlertTriangle size={17} /><span>Não foi possível carregar a API: {apiError}</span><button className="text-button" onClick={loadEmbeddings}>Tentar novamente</button></div>}
        <section className="registry-table-wrap embeddings-table-wrap"><table className="registry-table"><thead><tr><th>EMBEDDING</th><th>PESSOA</th><th>MODELO</th><th>ÂNGULO</th><th>DIMENSÃO</th><th>VETOR FACIAL</th><th></th></tr></thead><tbody>
          {loadingEmbeddings ? <tr><td colSpan="7" className="table-state"><LoaderCircle className="spin" size={20} /> Carregando embeddings</td></tr> : filteredEmbeddings.length === 0 ? <tr><td colSpan="7" className="table-state">Nenhuma embedding encontrada.</td></tr> : filteredEmbeddings.map((embedding) => <tr key={embedding.id}>
            <td><span className="embedding-count"><Fingerprint size={15} /> #{embedding.id}</span></td><td><div className="person-cell"><span className="person-avatar"><UserRound size={16} /></span><span><strong>{embedding.person?.name ?? `Pessoa #${embedding.person_id}`}</strong><small>ID {String(embedding.person_id).padStart(4, '0')}</small></span></div></td><td>{embedding.model}</td><td>{embedding.angle}</td><td>{embedding.dimension}</td><td><details className="stored-vector"><summary>Ver vetor</summary><code>{JSON.stringify(embedding.embedding)}</code></details></td><td><div className="row-actions"><IconButton label="Editar embedding" onClick={() => setEmbeddingModal({ person: embedding.person ?? { id: embedding.person_id, name: `Pessoa #${embedding.person_id}` }, embedding })}><Pencil size={15} /></IconButton><IconButton label="Remover embedding" danger onClick={() => deleteEmbedding(embedding.person ?? { id: embedding.person_id, name: `Pessoa #${embedding.person_id}` }, embedding)}><Trash2 size={15} /></IconButton></div></td>
          </tr>)}
        </tbody></table></section>
      </section>}
    </main>

    {personModal && <Modal title={personModal.person ? 'Editar pessoa' : personModal.detection ? 'Cadastrar pessoa e atrelar embedding' : 'Cadastrar pessoa'} onClose={() => setPersonModal(null)}><form className="form-content" onSubmit={savePerson}>
      <label>Nome completo<input name="name" required maxLength="100" defaultValue={personModal.person?.name ?? ''} placeholder="Nome e sobrenome" /></label>
      <label>Data de nascimento<input name="date_birth" required inputMode="numeric" maxLength="10" placeholder="dd/mm/aaaa" pattern="\d{2}/\d{2}/\d{4}" title="Use o formato dd/mm/aaaa" defaultValue={isoToBr(personModal.person?.date_birth)} onInput={(event) => { event.target.value = maskDate(event.target.value); }} /></label>
      <label className="toggle-field"><span><strong>Procurado pela justiça</strong><small>Marque se houver alerta ativo.</small></span><input name="wanted" type="checkbox" defaultChecked={personModal.person?.wanted ?? false} /></label>
      {personModal.detection && <label>Ângulo da embedding<input name="angle" required maxLength="20" defaultValue="frontal" placeholder="Ex.: frontal, diagonal" /></label>}
      <label>Motivo do alerta<textarea name="reason" maxLength="200" rows="3" defaultValue={personModal.person?.reason ?? ''} placeholder="Motivo (opcional)" /></label>
      <div className="modal-actions"><button className="button button-quiet" type="button" onClick={() => setPersonModal(null)}>Cancelar</button><button className="button button-accent" type="submit"><Check size={16} /> Salvar cadastro</button></div>
    </form></Modal>}
    {assignModal && <Modal title="Atrelar embedding a uma pessoa" onClose={() => setAssignModal(null)}><form className="form-content" onSubmit={(event) => {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      attachEmbedding(Number(form.get('person_id')), assignModal.detection, form.get('angle'));
    }}>
      <label>Pessoa cadastrada<select name="person_id" required defaultValue="">
        <option value="" disabled>Selecione uma pessoa</option>
        {people.map((person) => <option key={person.id} value={person.id}>{person.name} (#{person.id})</option>)}
      </select></label>
      <label>Ângulo<input name="angle" required maxLength="20" defaultValue="frontal" /></label>
      <div className="modal-actions">
        <button className="button button-quiet" type="button" onClick={() => { setPersonModal({ person: null, detection: assignModal.detection }); setAssignModal(null); }}><Plus size={16} /> Cadastrar nova pessoa</button>
        <button className="button button-accent" type="submit" disabled={!people.length}><Check size={16} /> Atrelar</button>
      </div>
    </form></Modal>}
    {embeddingModal && <Modal title={embeddingModal.embedding ? 'Editar embedding facial' : 'Adicionar embedding facial'} wide onClose={() => setEmbeddingModal(null)}><form className="form-content" onSubmit={saveEmbedding}>
      <div className="embedding-person-hint"><Fingerprint size={16} /> Associada a <strong>{embeddingModal.person.name}</strong></div>
      <div className="form-two"><label>Modelo<input name="model" required maxLength="20" defaultValue={embeddingModal.embedding?.model ?? ''} placeholder="Ex.: ArcFace" /></label><label>Ângulo<input name="angle" required maxLength="20" defaultValue={embeddingModal.embedding?.angle ?? ''} placeholder="Ex.: frontal" /></label></div>
      <label>Vetor facial · 512 valores<textarea name="embedding" required rows="7" defaultValue={embeddingModal.embedding?.embedding?.join(', ') ?? ''} placeholder="Cole os 512 valores separados por vírgula ou espaço" /></label>
      <div className="vector-hint">O serviço valida se o vetor contém exatamente 512 números.</div>
      <div className="modal-actions"><button className="button button-quiet" type="button" onClick={() => setEmbeddingModal(null)}>Cancelar</button><button className="button button-accent" type="submit"><Check size={16} /> Salvar embedding</button></div>
    </form></Modal>}
    {toast && <div className="toast" role="status"><Check size={16} />{toast}<IconButton label="Dispensar" onClick={() => setToast('')}><X size={14} /></IconButton></div>}
  </div>;
}

export default App;