export interface User {
  id: number;
  email: string;
  displayName: string;
  role: string;
  status: string;
  isVerified: boolean;
  gridCell: string | null;
  gridCenter: [number, number] | null;
}

export interface Dog {
  id: number;
  ownerId: number;
  name: string;
  breed: string;
  size: string;
  temperament: string;
  photoUrl: string | null;
}

export interface Mate {
  userId: number;
  displayName: string;
  isVerified: boolean;
  dogId: number;
  dogName: string;
  breed: string;
  size: string;
  temperament: string;
  approxDistanceM: number;
  gridCenter: [number, number];
}

export interface MatchItem {
  matchId: number;
  mateUserId: number;
  mateName: string;
  isVerified: boolean;
  dogName: string;
  breed: string;
  size: string;
  temperament: string;
  score: number;
  approxDistanceM: number;
  state: string;
}

export interface JobStatus {
  jobId: number;
  requestId: number;
  status: "queued" | "running" | "success" | "failed";
  progress: number;
  matches: MatchItem[];
  error: string | null;
}

export interface MeetingPlace {
  id: number;
  name: string;
  address: string;
  lat: number;
  lng: number;
}

export interface Message {
  id: number;
  matchId: number;
  senderId: number;
  body: string;
  createdAt: string;
}
