// A number input whose value is shown in the chosen unit but kept exactly in km, so switching units does not
// drift the value (850 km/h -> 528.15 mph -> back to exactly 850 km/h). A unit conversion, not geodesy.

/** input: the <input type=number>; km: initial value in km (or null for an empty field). */
export function unitField(input, km = null) {
  let factor = 1;                       // km per shown unit
  const state = { km, shown: null };
  const show = () => {
    input.value = state.km == null ? '' : String(Number((state.km / factor).toPrecision(5)));
    state.shown = input.value;
  };
  // Must be registered before any other 'change' listener, so getKm() is already right when they run.
  input.addEventListener('change', () => {
    const v = input.valueAsNumber;
    state.km = Number.isFinite(v) ? v * factor : null;
    state.shown = input.value;
  });
  return {
    setFactor(newFactor) { factor = newFactor; show(); },
    /** Value in km, or null when the field is empty or invalid. */
    getKm() {
      if (input.value === state.shown) return state.km;
      const v = input.valueAsNumber;
      return Number.isFinite(v) ? v * factor : null;
    },
  };
}
