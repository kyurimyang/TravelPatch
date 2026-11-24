import type { MouseEvent } from "react";
import "./DateField.css";

type Props = {
  id: string;
  value: string;
  min?: string;
  onChange: (iso: string) => void;
  placeholder?: string;
};

const WEEK = ["일", "월", "화", "수", "목", "금", "토"];

/** "11월 24일 (화)" for an ISO date, read as the trip's own calendar day. */
export function koDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  return `${d.getUTCMonth() + 1}월 ${d.getUTCDate()}일 (${WEEK[d.getUTCDay()]})`;
}

// A date input that shows the date in Korean. The browser's own field prints its locale's
// format ("mm/dd/yyyy" on an English system, 2026-11-25), so the real <input type="date"> sits
// on top, transparent: tapping anywhere opens the native picker, and keyboards still type in it.
export function DateField({
  id,
  value,
  min,
  onChange,
  placeholder = "날짜 고르기",
}: Props) {
  function open(e: MouseEvent<HTMLInputElement>) {
    try {
      e.currentTarget.showPicker?.();
    } catch {
      // some browsers only allow it from certain gestures: the field still works by keyboard
    }
  }
  return (
    <div className="date-field">
      <span
        className={
          value
            ? "date-field__text"
            : "date-field__text date-field__text--empty"
        }
        aria-hidden="true"
      >
        {value ? koDate(value) : placeholder}
      </span>
      <svg
        className="date-field__icon"
        aria-hidden="true"
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      >
        <rect x="4" y="5.5" width="16" height="14" rx="2.5" />
        <path d="M4 10h16M8.5 3.5v4M15.5 3.5v4" />
      </svg>
      <input
        id={id}
        type="date"
        min={min}
        value={value}
        onClick={open}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
