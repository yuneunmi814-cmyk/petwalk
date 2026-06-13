import { useState } from "react";
import { api } from "../api";
import type { Dog, User } from "../types";
import { Banner, dogEmoji, SIZE_KO, TEMPER_KO } from "../ui";

const DEMO_LAT = 37.5172;
const DEMO_LNG = 127.0473;

export function DogsTab({
  user,
  dogs,
  reloadDogs,
  onUser,
}: {
  user: User;
  dogs: Dog[];
  reloadDogs: () => Promise<void>;
  onUser: (u: User) => void;
}) {
  const blank = { name: "", breed: "", size: "medium", temperament: "playful" };
  const [form, setForm] = useState(blank);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await api.addDog(form);
      setForm(blank);
      await reloadDogs();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    if (!confirm("이 강아지 프로필을 삭제할까요?")) return;
    await api.deleteDog(id);
    await reloadDogs();
  }

  async function setDemoLocation() {
    onUser(await api.setLocation(DEMO_LAT, DEMO_LNG));
  }

  return (
    <div className="stack">
      <div className="card">
        <div className="spread">
          <h2>내 위치</h2>
          {user.gridCell ? (
            <span className="badge badge-primary">그리드 {user.gridCell}</span>
          ) : (
            <span className="badge badge-accent">미설정</span>
          )}
        </div>
        <p className="muted" style={{ marginTop: 8 }}>
          정확한 GPS 좌표는 서버에만 저장되고, 다른 사용자에게는 약 300m 격자의 중심만 노출돼요.
          {user.gridCenter && (
            <>
              {" "}
              현재 노출 위치: 약 [{user.gridCenter[0].toFixed(4)}, {user.gridCenter[1].toFixed(4)}]
            </>
          )}
        </p>
        <button className="btn btn-ghost btn-sm" style={{ marginTop: 8 }} onClick={setDemoLocation}>
          📍 내 동네를 강남 데모 위치로 설정
        </button>
      </div>

      <div className="card">
        <h2>강아지 등록</h2>
        {err && <Banner kind="err">{err}</Banner>}
        <form onSubmit={add} style={{ marginTop: err ? 12 : 0 }}>
          <div className="grid2">
            <div className="field">
              <label>이름</label>
              <input
                value={form.name}
                required
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="몽이"
              />
            </div>
            <div className="field">
              <label>견종</label>
              <input
                value={form.breed}
                required
                onChange={(e) => setForm({ ...form, breed: e.target.value })}
                placeholder="믹스"
              />
            </div>
          </div>
          <div className="grid2">
            <div className="field">
              <label>크기</label>
              <select value={form.size} onChange={(e) => setForm({ ...form, size: e.target.value })}>
                {Object.entries(SIZE_KO).map(([v, k]) => (
                  <option key={v} value={v}>
                    {k}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>성향</label>
              <select
                value={form.temperament}
                onChange={(e) => setForm({ ...form, temperament: e.target.value })}
              >
                {Object.entries(TEMPER_KO).map(([v, k]) => (
                  <option key={v} value={v}>
                    {k}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <button className="btn btn-primary btn-block" disabled={busy}>
            {busy ? "등록 중…" : "+ 강아지 추가"}
          </button>
        </form>
      </div>

      <div className="stack">
        <div className="section-title">내 강아지 ({dogs.length})</div>
        {dogs.length === 0 && <div className="empty">아직 등록한 강아지가 없어요.</div>}
        {dogs.map((d) => (
          <div className="tile" key={d.id}>
            <div className="avatar">{dogEmoji(d.size)}</div>
            <div className="meta">
              <div className="name">{d.name}</div>
              <div className="sub">
                {d.breed} · {SIZE_KO[d.size]} · {TEMPER_KO[d.temperament]}
              </div>
            </div>
            <button className="btn btn-danger btn-sm" onClick={() => remove(d.id)}>
              삭제
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
