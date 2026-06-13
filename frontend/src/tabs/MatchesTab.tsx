import { useEffect, useRef, useState } from "react";
import { api, ApiError, chatSocketUrl } from "../api";
import type { MatchItem, Message, User } from "../types";
import { Banner, distanceLabel, dogEmoji, Empty, SIZE_KO, Stars, TEMPER_KO, Verified } from "../ui";

export function MatchesTab({ user }: { user: User }) {
  const [matches, setMatches] = useState<MatchItem[] | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);

  const reload = () => api.myMatches().then(setMatches);
  useEffect(() => {
    reload();
  }, []);

  if (!matches) return <div className="muted">불러오는 중…</div>;
  if (matches.length === 0)
    return <Empty>아직 확정된 매칭이 없어요. ‘메이트 찾기’에서 산책을 요청해보세요.</Empty>;

  return (
    <div className="stack">
      {matches.map((m) => (
        <MatchCard
          key={m.matchId}
          m={m}
          user={user}
          open={openId === m.matchId}
          onToggle={() => setOpenId(openId === m.matchId ? null : m.matchId)}
        />
      ))}
    </div>
  );
}

function MatchCard({
  m,
  user,
  open,
  onToggle,
}: {
  m: MatchItem;
  user: User;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="card">
      <div className="tile" style={{ border: "none", padding: 0 }}>
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
        <button className="btn btn-sm" onClick={onToggle}>
          {open ? "닫기" : "채팅 · 후기"}
        </button>
      </div>

      {open && (
        <div style={{ marginTop: 14 }}>
          <Chat matchId={m.matchId} userId={user.id} />
          <hr style={{ border: "none", borderTop: "1px solid var(--line)", margin: "16px 0" }} />
          <ReviewBox matchId={m.matchId} />
          <ReportButton targetUserId={m.mateUserId} mateName={m.mateName} />
        </div>
      )}
    </div>
  );
}

function Chat({ matchId, userId }: { matchId: number; userId: number }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const [live, setLive] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const upsert = (msg: Message) =>
    setMessages((prev) => (prev.some((m) => m.id === msg.id) ? prev : [...prev, msg]));

  // Load history once via REST, then open the live socket.
  useEffect(() => {
    let alive = true;
    api.messages(matchId).then((m) => alive && setMessages(m)).catch(() => {});

    const ws = new WebSocket(chatSocketUrl(matchId));
    wsRef.current = ws;
    ws.onopen = () => alive && setLive(true);
    ws.onmessage = (e) => {
      try {
        upsert(JSON.parse(e.data) as Message);
      } catch {
        /* ignore malformed frame */
      }
    };
    ws.onclose = () => alive && setLive(false);
    ws.onerror = () => {};

    return () => {
      alive = false;
      ws.close();
      wsRef.current = null;
    };
  }, [matchId]);

  // Graceful fallback: poll history whenever the socket isn't live.
  useEffect(() => {
    if (live) return;
    let alive = true;
    const t = setInterval(async () => {
      try {
        const m = await api.messages(matchId);
        if (alive) setMessages(m);
      } catch {
        /* ignore */
      }
    }, 3000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [live, matchId]);

  useEffect(() => {
    boxRef.current?.scrollTo(0, boxRef.current.scrollHeight);
  }, [messages]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const body = text.trim();
    if (!body) return;
    setText("");
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ body })); // server echoes it back with its id
    } else {
      upsert(await api.sendMessage(matchId, body));
    }
  }

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="section-title">채팅</div>
        <span className="muted" style={{ fontSize: 12 }}>
          {live ? "🟢 실시간 연결됨" : "⚪ 연결 중…"}
        </span>
      </div>
      <div className="chat" ref={boxRef}>
        {messages.length === 0 && (
          <div className="muted" style={{ fontSize: 13 }}>첫 메시지를 보내보세요 👋</div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`msg ${msg.senderId === userId ? "mine" : ""}`}>
            {msg.body}
          </div>
        ))}
      </div>
      <form className="row" style={{ marginTop: 8 }} onSubmit={send}>
        <input
          className="grow"
          style={{ padding: "10px 12px", border: "1px solid var(--line)", borderRadius: 10 }}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="메시지 입력…"
        />
        <button className="btn btn-primary">전송</button>
      </form>
    </div>
  );
}

function ReviewBox({ matchId }: { matchId: number }) {
  const [score, setScore] = useState(5);
  const [comment, setComment] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function submit() {
    setErr(null);
    try {
      await api.review(matchId, score, comment);
      setDone("후기가 등록되었어요. 감사합니다!");
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) setErr("이미 이 산책에 후기를 남겼어요.");
      else setErr((e as Error).message);
    }
  }

  if (done) return <Banner kind="ok">{done}</Banner>;

  return (
    <div>
      <div className="section-title">산책 후기</div>
      {err && <Banner kind="err">{err}</Banner>}
      <div className="row" style={{ margin: "6px 0" }}>
        <Stars value={score} onChange={setScore} />
        <span className="muted">{score}점</span>
      </div>
      <div className="field">
        <textarea
          rows={2}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="산책은 어땠나요? (선택)"
        />
      </div>
      <button className="btn btn-primary btn-sm" onClick={submit}>
        후기 등록
      </button>
    </div>
  );
}

function ReportButton({ targetUserId, mateName }: { targetUserId: number; mateName: string }) {
  const [done, setDone] = useState(false);
  async function report() {
    const reason = prompt(`${mateName}님을 신고하는 사유를 입력하세요 (노쇼, 부적절 행동 등)`);
    if (!reason) return;
    await api.report(targetUserId, reason);
    setDone(true);
  }
  if (done)
    return (
      <p className="muted" style={{ fontSize: 13, marginTop: 12 }}>
        신고가 접수되었고 즉시 차단되었어요.
      </p>
    );
  return (
    <button className="btn btn-danger btn-sm" style={{ marginTop: 12 }} onClick={report}>
      🚩 신고 · 차단
    </button>
  );
}
