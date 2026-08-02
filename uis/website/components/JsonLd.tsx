import { WebsiteContent } from "@/types/website";

interface JsonLdProps {
  content: WebsiteContent;
}

const toSchemaPhone = (phone: string): string => {
  const digits = phone.replace(/\D/g, "");
  if (digits.length === 10) {
    return `+1-${digits.slice(0, 3)}-${digits.slice(3, 6)}-${digits.slice(6)}`;
  }

  return phone;
};

export default function JsonLd({ content }: JsonLdProps) {
  const graph = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "MedicalOrganization",
        "@id": "https://www.healthcore.com/#organization",
        name: "HealthCore",
        description:
          "Outpatient healthcare network offering primary care, specialist consultations, chronic disease management, and preventive health programmes.",
        url: "https://www.healthcore.com",
        foundingDate: "2011",
        logo: "https://www.healthcore.com/logo.png",
        availableLanguage: ["English", "Spanish"],
        areaServed: ["US", "GB"],
        address: {
          "@type": "PostalAddress",
          addressLocality: "Austin",
          addressRegion: "Texas",
          addressCountry: "US",
        },
        contactPoint: {
          "@type": "ContactPoint",
          telephone: "+1-512-340-8800",
          contactType: "patient services",
          availableLanguage: ["English", "Spanish"],
        },
        sameAs: [
          "https://linkedin.com/company/healthcore",
          "https://facebook.com/healthcore",
          "https://instagram.com/healthcore",
        ],
      },
      ...content.locations.map((clinic) => ({
        "@type": "MedicalClinic",
        name: clinic.name,
        telephone: toSchemaPhone(clinic.phone),
        openingHours: clinic.schemaHours,
        parentOrganization: { "@id": "https://www.healthcore.com/#organization" },
      })),
    ],
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(graph) }}
    />
  );
}
