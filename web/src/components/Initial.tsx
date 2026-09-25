/** 사진 대신 닉네임 첫 글자 */
export function Initial({ name, size = 44 }: { name: string; size?: number }) {
  return (
    <span
      aria-hidden
      className="flex shrink-0 items-center justify-center rounded-full border border-line-strong bg-paper-card font-serif font-semibold text-ink-soft"
      style={{ width: size, height: size, fontSize: size * 0.4 }}
    >
      {name.slice(0, 1)}
    </span>
  );
}
