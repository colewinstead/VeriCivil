const paths = {
  left: "M19 12H5m6-6-6 6 6 6",
  right: "M5 12h14m-6-6 6 6-6 6",
  plus: "M5 12h14M12 5v14",
  minus: "M5 12h14",
  close: "m6 6 12 12M6 18 18 6",
  chevron: "m9 5 7 7-7 7",
};

export default function ControlIcon({ name }: { name: keyof typeof paths }) {
  return <svg aria-hidden="true" focusable="false" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ verticalAlign: "middle" }}><path d={paths[name]} /></svg>;
}
