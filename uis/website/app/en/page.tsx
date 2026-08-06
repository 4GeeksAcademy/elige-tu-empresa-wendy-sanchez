import type { Metadata } from "next";
import LandingPage from "@/components/LandingPage";
import JsonLd from "@/components/JsonLd";
import { englishContent } from "@/data/content";

export const metadata: Metadata = {
  title: englishContent.title,
  description: englishContent.description,
};

export default function EnglishHomePage() {
  return (
    <>
      <JsonLd content={englishContent} />
      <LandingPage content={englishContent} />
    </>
  );
}
