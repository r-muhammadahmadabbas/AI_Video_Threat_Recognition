import { notFound } from "next/navigation";
import { StyleguideContent } from "./styleguide-content";

export default function StyleguidePage() {
  if (process.env.NODE_ENV === "production") notFound();
  return <StyleguideContent />;
}
