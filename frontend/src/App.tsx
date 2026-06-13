import { useEffect, useState } from "react";
import { api, getToken, setToken } from "./api";
import type { Dog, User } from "./types";
import { DogsTab } from "./tabs/DogsTab";
import { FindTab } from "./tabs/FindTab";
import { MatchesTab } from "./tabs/MatchesTab";
import { Banner } from "./ui";
import { DEMO_LAT, DEMO_LNG, getDeviceLocation, isNative } from "./location";

type Tab = "dogs" | "find" | "matches";

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [booting, setBooting] = useState(true);

  useEffect(() => {
    (async () => {
      if (getToken()) {
        try {
          setUser(await api.me());
        } catch {
          setToken(null);
        }
      }
      setBooting(false);
    })();
  }, []);

  if (booting) return <div className="center muted">불러오는 중…</div>;
  if (!user) return <AuthView onAuthed={setUser} />;
  return <Shell user={user} setUser={setUser} onLogout={() => { setToken(null); setUser(null); }} />;
}

function Shell({
  user,
  setUser,
  onLogout,
}: {
  user: User;
  setUser: (u: User) => void;
  onLogout: () => void;
}) {
  const [tab, setTab] = useState<Tab>("find");
  const [dogs, setDogs] = useState<Dog[]>([]);

  const reloadDogs = async () => setDogs(await api.dogs());
  useEffect(() => {
    reloadDogs();
  }, []);

  return (
    <>
      <header className="topbar">
        <div className="brand">
          <span className="logo">🐾</span> PetWalk <small>산책 메이트</small>
        </div>
        <div className="who">
          <span>
            {user.displayName}님{user.role === "admin" ? " (관리자)" : ""}
          </span>
          <button className="btn btn-ghost btn-sm" onClick={onLogout}>
            로그아웃
          </button>
        </div>
      </header>

      <nav className="tabs">
        <button className={`tab ${tab === "dogs" ? "active" : ""}`} onClick={() => setTab("dogs")}>
          내 강아지
        </button>
        <button className={`tab ${tab === "find" ? "active" : ""}`} onClick={() => setTab("find")}>
          메이트 찾기
        </button>
        <button
          className={`tab ${tab === "matches" ? "active" : ""}`}
          onClick={() => setTab("matches")}
        >
          내 매칭
        </button>
      </nav>

      <main className="container">
        {tab === "dogs" && (
          <DogsTab user={user} dogs={dogs} reloadDogs={reloadDogs} onUser={setUser} />
        )}
        {tab === "find" && (
          <FindTab user={user} dogs={dogs} goToMatches={() => setTab("matches")} />
        )}
        {tab === "matches" && <MatchesTab user={user} />}
      </main>
    </>
  );
}

function AuthView({ onAuthed }: { onAuthed: (u: User) => void }) {
  const [mode, setMode] = useState<"login" | "signup">("signup");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [useDemoLoc, setUseDemoLoc] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      if (mode === "signup") {
        let loc: { lat: number; lng: number } | undefined;
        if (useDemoLoc) {
          try {
            loc = isNative() ? await getDeviceLocation() : { lat: DEMO_LAT, lng: DEMO_LNG };
          } catch {
            loc = { lat: DEMO_LAT, lng: DEMO_LNG }; // GPS denied/timeout → demo fallback
          }
        }
        const res = await api.signup({ email, password, displayName, ...(loc ?? {}) });
        setToken(res.accessToken);
        onAuthed(res.user);
      } else {
        const { accessToken } = await api.login(email, password);
        setToken(accessToken);
        onAuthed(await api.me());
      }
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="card auth-card">
        <div className="hero">
          <div className="logo">🐾</div>
          <h1>PetWalk</h1>
          <p>동네 반려견 산책 메이트 매칭</p>
        </div>

        {err && <Banner kind="err">{err}</Banner>}

        <form onSubmit={submit} style={{ marginTop: err ? 12 : 0 }}>
          {mode === "signup" && (
            <div className="field">
              <label>닉네임</label>
              <input value={displayName} required onChange={(e) => setDisplayName(e.target.value)} placeholder="멍멍이집사" />
            </div>
          )}
          <div className="field">
            <label>이메일</label>
            <input type="email" value={email} required onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
          </div>
          <div className="field">
            <label>비밀번호</label>
            <input
              type="password"
              value={password}
              required
              minLength={8}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="8자 이상"
            />
          </div>
          {mode === "signup" && (
            <label className="row" style={{ fontSize: 13, color: "var(--muted)", marginBottom: 12 }}>
              <input type="checkbox" checked={useDemoLoc} onChange={(e) => setUseDemoLoc(e.target.checked)} />
              {isNative()
                ? "현재 위치(GPS)로 주변 메이트 찾기"
                : "내 동네를 강남 데모 위치로 설정 (주변 메이트 바로 보기)"}
            </label>
          )}
          <button className="btn btn-primary btn-block" disabled={busy}>
            {busy ? "처리 중…" : mode === "signup" ? "시작하기" : "로그인"}
          </button>
        </form>

        <div className="switch">
          {mode === "signup" ? "이미 계정이 있나요?" : "처음이신가요?"}{" "}
          <button onClick={() => { setMode(mode === "signup" ? "login" : "signup"); setErr(null); }}>
            {mode === "signup" ? "로그인" : "회원가입"}
          </button>
        </div>
      </div>
    </div>
  );
}
