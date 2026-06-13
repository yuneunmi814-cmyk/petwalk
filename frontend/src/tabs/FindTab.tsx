import { useEffect, useState } from "react";
import { api, sleep } from "../api";
import type { Dog, JobStatus, MatchItem, Mate, MeetingPlace, User } from "../types";
import {
  Banner,
  distanceLabel,
  dogEmoji,
  Empty,
  Progress,
  SIZE_KO,
  TEMPER_KO,
  Verified,
} from "../ui";

function defaultSlot(): string {
  const d = new Date(Date.now() + 24 * 3600 * 1000);
  d.setHours(18, 0, 0, 0);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(
    d.getMinutes()
  )}`;
}

const STATUS_KO: Record<string, string> = {
  queued: "대기열에 추가됨…",
  running: "후보 적합도 계산 중…",
  success: "매칭 후보를 찾았어요",
  failed: "처리에 실패했어요",
};

export function FindTab({ user, dogs, goToMatches }: { user: User; dogs: Dog[]; goToMatches: () => void }) {
  const [mates, setMates] = useState<Mate[] | null>(null);
  const [dogId, setDogId] = useState<number | undefined>(dogs[0]?.id);
  const [timeSlot, setTimeSlot] = useState(defaultSlot());
  const [radiusKm, setRadiusKm] = useState(2);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [running, setRunning] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [acceptFor, setAcceptFor] = useState<MatchItem | null>(null);
  const [places, setPlaces] = useState<MeetingPlace[]>([]);
  const [confirmed, setConfirmed] = useState<{ mate: string; place: string } | null>(null);

  useEffect(() => {
    api.mates().then((r) => setMates(r.items)).catch(() => setMates([]));
  }, []);
  useEffect(() => {
    if (!dogId && dogs[0]) setDogId(dogs[0].id);
  }, [dogs, dogId]);

  async function request(e: React.FormEvent) {
    e.preventDefault();
    if (!dogId) {
      setErr("먼저 ‘내 강아지’ 탭에서 강아지를 등록하세요.");
      return;
    }
    setErr(null);
    setConfirmed(null);
    setRunning(true);
    setJob({ jobId: 0, requestId: 0, status: "queued", progress: 5, matches: [], error: null });
    try {
      const { statusUrl } = await api.requestWalk({ dogId, timeSlot, radiusKm });
      // Poll the async job until it settles (design §1.2 step 3).
      for (;;) {
        await sleep(700);
        const s = await api.job(statusUrl);
        setJob(s);
        if (s.status === "success" || s.status === "failed") break;
      }
    } catch (e) {
      setErr((e as Error).message);
      setJob(null);
    } finally {
      setRunning(false);
    }
  }

  async function openAccept(m: MatchItem) {
    setAcceptFor(m);
    if (places.length === 0) setPlaces(await api.places());
  }

  async function confirmAccept(placeId: number) {
    const m = acceptFor!;
    const res = await api.accept(m.matchId, placeId);
    setAcceptFor(null);
    setConfirmed({ mate: m.mateName, place: res.meetingPlace.name });
    setJob((j) =>
      j
        ? {
            ...j,
            matches: j.matches.map((x) =>
              x.matchId === m.matchId
                ? { ...x, state: "confirmed" }
                : x.state === "suggested"
                ? { ...x, state: "declined" }
                : x
            ),
          }
        : j
    );
  }

  const hasLocation = !!user.gridCell;

  return (
    <div className="stack">
      <div className="card">
        <h2>🦴 산책 메이트 요청</h2>
        {!hasLocation && (
          <Banner kind="info">‘내 강아지’ 탭에서 위치를 먼저 설정하면 주변 메이트를 찾을 수 있어요.</Banner>
        )}
        {err && <Banner kind="err">{err}</Banner>}
        <form onSubmit={request} style={{ marginTop: 12 }}>
          <div className="field">
            <label>함께 산책할 내 강아지</label>
            <select value={dogId ?? ""} onChange={(e) => setDogId(Number(e.target.value))}>
              {dogs.length === 0 && <option value="">등록된 강아지 없음</option>}
              {dogs.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} ({d.breed})
                </option>
              ))}
            </select>
          </div>
          <div className="grid2">
            <div className="field">
              <label>희망 시간</label>
              <input
                type="datetime-local"
                value={timeSlot}
                onChange={(e) => setTimeSlot(e.target.value)}
              />
            </div>
            <div className="field">
              <label>반경 {radiusKm}km</label>
              <input
                type="range"
                min={1}
                max={5}
                step={1}
                value={radiusKm}
                onChange={(e) => setRadiusKm(Number(e.target.value))}
              />
            </div>
          </div>
          <button className="btn btn-primary btn-block" disabled={running || !hasLocation || dogs.length === 0}>
            {running ? "요청 처리 중…" : "산책 메이트 찾기"}
          </button>
        </form>

        {job && (
          <div style={{ marginTop: 16 }}>
            <div className="spread" style={{ marginBottom: 6 }}>
              <span className="muted">{STATUS_KO[job.status]}</span>
              <span className="muted">{job.progress}%</span>
            </div>
            <Progress value={job.progress} />
          </div>
        )}

        {confirmed && (
          <div style={{ marginTop: 14 }}>
            <Banner kind="ok">
              <b>{confirmed.mate}</b>님과 매칭 확정! 첫 만남 장소: <b>{confirmed.place}</b>.{" "}
              <button className="btn btn-ghost btn-sm" onClick={goToMatches}>
                채팅하러 가기 →
              </button>
            </Banner>
          </div>
        )}
      </div>

      {job?.status === "success" && (
        <div className="stack">
          <div className="section-title">매칭 후보 ({job.matches.length}) — 적합도 순</div>
          {job.matches.length === 0 && (
            <Empty>반경 내에 적합한 메이트가 없어요. 반경을 넓혀보세요.</Empty>
          )}
          {job.matches.map((m) => (
            <div className="tile" key={m.matchId}>
              <div className="avatar">{dogEmoji(m.size)}</div>
              <div className="meta">
                <div className="name">
                  {m.dogName} <span className="muted" style={{ fontWeight: 400 }}>· {m.mateName}</span>
                  {m.isVerified && <Verified />}
                </div>
                <div className="sub">
                  {m.breed} · {SIZE_KO[m.size]} · {TEMPER_KO[m.temperament]} · 약 {distanceLabel(m.approxDistanceM)}
                </div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div className="score-pill" title="적합도 점수">{Math.round(m.score)}</div>
                <div style={{ marginTop: 6 }}>
                  {m.state === "confirmed" ? (
                    <span className="badge badge-primary">✓ 확정</span>
                  ) : m.state === "declined" ? (
                    <span className="badge">마감</span>
                  ) : (
                    <button className="btn btn-primary btn-sm" onClick={() => openAccept(m)}>
                      수락
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="stack">
        <div className="section-title">내 주변 메이트</div>
        {mates === null && <div className="muted">불러오는 중…</div>}
        {mates !== null && mates.length === 0 && <Empty>주변에 등록된 메이트가 아직 없어요.</Empty>}
        <div className="mate-grid">
          {mates?.map((mate) => (
            <div className="tile" key={`${mate.userId}-${mate.dogId}`}>
              <div className="avatar">{dogEmoji(mate.size)}</div>
              <div className="meta">
                <div className="name">
                  {mate.dogName}
                  {mate.isVerified && <Verified />}
                </div>
                <div className="sub">
                  {SIZE_KO[mate.size]} · {TEMPER_KO[mate.temperament]} · 약 {distanceLabel(mate.approxDistanceM)}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {acceptFor && (
        <PlacePicker
          mate={acceptFor.mateName}
          places={places}
          onClose={() => setAcceptFor(null)}
          onConfirm={confirmAccept}
        />
      )}
    </div>
  );
}

function PlacePicker({
  mate,
  places,
  onClose,
  onConfirm,
}: {
  mate: string;
  places: MeetingPlace[];
  onClose: () => void;
  onConfirm: (placeId: number) => void;
}) {
  const [sel, setSel] = useState<number | null>(places[0]?.id ?? null);
  const [busy, setBusy] = useState(false);
  // places may arrive after the sheet mounts — default to the first once loaded.
  useEffect(() => {
    if (sel === null && places.length) setSel(places[0].id);
  }, [places, sel]);
  return (
    <div className="overlay" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <h2 style={{ marginBottom: 6 }}>첫 만남 장소 선택</h2>
        <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
          안전을 위해 첫 만남은 공개 장소에서만 가능해요. {mate}님과 만날 곳을 골라주세요.
        </p>
        <div style={{ margin: "12px 0" }}>
          {places.map((p) => (
            <label key={p.id} className={`place-opt ${sel === p.id ? "sel" : ""}`}>
              <input
                type="radio"
                name="place"
                checked={sel === p.id}
                onChange={() => setSel(p.id)}
                style={{ marginTop: 3 }}
              />
              <span>
                <b>{p.name}</b>
                <br />
                <span className="muted" style={{ fontSize: 13 }}>{p.address}</span>
              </span>
            </label>
          ))}
        </div>
        <div className="row">
          <button className="btn btn-ghost grow" onClick={onClose}>
            취소
          </button>
          <button
            className="btn btn-primary grow"
            disabled={sel === null || busy}
            onClick={async () => {
              setBusy(true);
              try {
                await onConfirm(sel!);
              } finally {
                setBusy(false);
              }
            }}
          >
            매칭 확정
          </button>
        </div>
      </div>
    </div>
  );
}
