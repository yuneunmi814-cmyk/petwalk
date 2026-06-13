import type {
  Dog,
  JobStatus,
  MatchItem,
  Mate,
  MeetingPlace,
  Message,
  User,
} from "./types";

const TOKEN_KEY = "petwalk.token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((opts.headers as Record<string, string>) || {}),
  };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(path, { ...opts, headers });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const err = data?.error ?? {};
    throw new ApiError(res.status, err.code ?? "error", err.message ?? res.statusText);
  }
  return data as T;
}

export interface SignupBody {
  email: string;
  password: string;
  displayName: string;
  lat?: number;
  lng?: number;
}
export interface DogBody {
  name: string;
  breed: string;
  size: string;
  temperament: string;
}
export interface WalkRequestBody {
  dogId: number;
  timeSlot: string;
  radiusKm: number;
}

interface TokenPair {
  accessToken: string;
  refreshToken: string;
}
interface SignupResult extends TokenPair {
  user: User;
}
interface MateList {
  items: Mate[];
  total: number;
  page: number;
}
interface JobAccepted {
  jobId: number;
  statusUrl: string;
}

export const api = {
  signup: (b: SignupBody) =>
    req<SignupResult>("/api/v1/auth/signup", { method: "POST", body: JSON.stringify(b) }),
  login: (email: string, password: string) =>
    req<TokenPair>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => req<User>("/api/v1/auth/me"),
  setLocation: (lat: number, lng: number) =>
    req<User>("/api/v1/auth/me/location", { method: "PATCH", body: JSON.stringify({ lat, lng }) }),

  dogs: () => req<Dog[]>("/api/v1/dogs"),
  addDog: (b: DogBody) => req<Dog>("/api/v1/dogs", { method: "POST", body: JSON.stringify(b) }),
  deleteDog: (id: number) => req<null>(`/api/v1/dogs/${id}`, { method: "DELETE" }),

  mates: () => req<MateList>("/api/v1/mates"),

  requestWalk: (b: WalkRequestBody) =>
    req<JobAccepted>("/api/v1/walk-requests", { method: "POST", body: JSON.stringify(b) }),
  job: (statusUrl: string) => req<JobStatus>(statusUrl),

  accept: (matchId: number, meetingPlaceId: number) =>
    req<{ matchId: number; state: string; meetingPlace: MeetingPlace }>(
      `/api/v1/matches/${matchId}/accept`,
      { method: "POST", body: JSON.stringify({ meetingPlaceId }) }
    ),
  myMatches: () => req<MatchItem[]>("/api/v1/matches"),
  places: () => req<MeetingPlace[]>("/api/v1/meeting-places"),

  messages: (matchId: number) => req<Message[]>(`/api/v1/matches/${matchId}/messages`),
  sendMessage: (matchId: number, body: string) =>
    req<Message>(`/api/v1/matches/${matchId}/messages`, {
      method: "POST",
      body: JSON.stringify({ body }),
    }),

  review: (matchId: number, score: number, comment: string) =>
    req<unknown>("/api/v1/reviews", {
      method: "POST",
      body: JSON.stringify({ matchId, score, comment }),
    }),
  report: (targetUserId: number, reason: string) =>
    req<unknown>("/api/v1/reports", {
      method: "POST",
      body: JSON.stringify({ targetUserId, reason }),
    }),
};

export const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
