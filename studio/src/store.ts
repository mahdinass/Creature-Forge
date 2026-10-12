import { create } from 'zustand'
import { advance, restart, type Clock } from './playback'

interface PlaybackState extends Clock {
  speed: number
  duration: number
  follow: boolean
  setDuration: (d: number) => void
  play: () => void
  pause: () => void
  toggle: () => void
  restart: () => void
  seek: (t: number) => void
  setSpeed: (s: number) => void
  setFollow: (f: boolean) => void
  tick: (wallDt: number) => void
}

// One shared clock drives every viewport, so side-by-side runs stay on the same simulation time.
export const usePlayback = create<PlaybackState>((set, get) => ({
  simTime: 0,
  replayTime: 0,
  playing: false,
  speed: 0.5,
  duration: 5,
  follow: true,
  setDuration: (duration) => set({ duration }),
  play: () => {
    const { simTime, duration } = get()
    set(simTime >= duration ? restart() : { playing: true })
  },
  pause: () => set({ playing: false }),
  toggle: () => (get().playing ? get().pause() : get().play()),
  restart: () => set(restart()),
  seek: (t) => set({ simTime: Math.max(0, Math.min(get().duration, t)), playing: false }),
  setSpeed: (speed) => set({ speed }),
  setFollow: (follow) => set({ follow }),
  tick: (wallDt) => {
    const s = get()
    if (!s.playing) return
    set(advance(s, wallDt, s.speed, s.duration))
  },
}))
