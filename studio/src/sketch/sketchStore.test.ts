import { beforeEach, describe, expect, it } from 'vitest'
import { useSketch } from './sketchStore'

beforeEach(() => useSketch.setState({ strokes: [], past: [], future: [], nextId: 1, pen: 'auto', guided: true }))

describe('sketch store', () => {
  it('adds strokes with the current pen role and supports undo and redo', () => {
    useSketch.getState().setPen('leg')
    useSketch.getState().addStroke([[0, 0], [10, 10], [20, 30]])
    useSketch.getState().addStroke([[5, 5], [50, 50]])
    expect(useSketch.getState().strokes.map((x) => x.role)).toEqual(['leg', 'leg'])
    useSketch.getState().undo()
    expect(useSketch.getState().strokes).toHaveLength(1)
    useSketch.getState().redo()
    expect(useSketch.getState().strokes).toHaveLength(2)
    useSketch.getState().undo()
    useSketch.getState().addStroke([[1, 1], [2, 2]])
    expect(useSketch.getState().future).toEqual([]) // a new action ends the redo history
  })
  it('erases whole strokes under the pointer as one undoable step', () => {
    useSketch.getState().addStroke([[0, 0], [100, 0]])
    useSketch.getState().addStroke([[0, 200], [100, 200]])
    useSketch.getState().beginErase()
    expect(useSketch.getState().eraseAt([50, 3], 10)).toBe(1)
    expect(useSketch.getState().strokes).toHaveLength(1)
    useSketch.getState().undo()
    expect(useSketch.getState().strokes).toHaveLength(2)
  })
  it('keeps the raw points exactly (no snapping or straightening) and lets roles be corrected', () => {
    const pts: [number, number][] = [[10, 10], [11.3, 52.7], [9.1, 90.2], [12.4, 140]]
    useSketch.getState().addStroke(pts)
    const st = useSketch.getState().strokes[0]
    expect(st.points[0]).toEqual(pts[0])
    expect(st.points[st.points.length - 1]).toEqual(pts[3])
    useSketch.getState().setRole(st.id, 'torso')
    expect(useSketch.getState().strokes[0].role).toBe('torso')
    useSketch.getState().undo()
    expect(useSketch.getState().strokes[0].role).toBe('auto')
  })
  it('clear is undoable and loading a starter keeps history', () => {
    useSketch.getState().addStroke([[0, 0], [30, 30]])
    useSketch.getState().clear()
    expect(useSketch.getState().strokes).toEqual([])
    useSketch.getState().undo()
    expect(useSketch.getState().strokes).toHaveLength(1)
    useSketch.getState().load([{ id: 'x', role: 'torso', points: [[0, 0], [5, 5]] }], { guided: false })
    expect(useSketch.getState().guided).toBe(false)
    expect(useSketch.getState().strokes[0].role).toBe('torso')
    useSketch.getState().undo()
    expect(useSketch.getState().strokes).toHaveLength(1)
  })
})
