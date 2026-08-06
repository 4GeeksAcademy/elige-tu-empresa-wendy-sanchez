import type { Metadata } from "next";
import LandingPage from "@/components/LandingPage";
import JsonLd from "@/components/JsonLd";
import { spanishContent } from "@/data/content";

export const metadata: Metadata = {
  title: spanishContent.title,
  description: spanishContent.description,
};

export default function SpanishHomePage() {
  return (
    <>
      <JsonLd content={spanishContent} />
      <LandingPage content={spanishContent} />
    </>
  );
}
