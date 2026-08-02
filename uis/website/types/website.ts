export interface NavItem {
  label: string;
  href: string;
}

export interface ServiceSection {
  title: string;
  bullets: string[];
}

export interface WhyItem {
  emphasis: string;
  text: string;
}

export interface ClinicLocation {
  name: string;
  city: string;
  state: string;
  phone: string;
  hours: string;
  schemaHours: string;
}

export interface ContactCard {
  title: string;
  value: string;
}

export interface WebsiteContent {
  lang: "en" | "es";
  title: string;
  description: string;
  navLabel: string;
  mobileNavLabel: string;
  homeAnchor: string;
  homeAriaLabel: string;
  navItems: NavItem[];
  heroBadge: string;
  heroTitle: string;
  heroSubtitle: string;
  heroPrimaryCta: string;
  heroSecondaryCta: string;
  heroImageAlt: string;
  servicesTitle: string;
  servicesSubtitle: string;
  services: ServiceSection[];
  whyTitle: string;
  whyItems: WhyItem[];
  whyCardTitle: string;
  whyCardBody: string;
  whyCardCta: string;
  locationsTitle: string;
  locationsNote: string;
  locationsTableLabel: string;
  locationsColumns: {
    clinic: string;
    city: string;
    state: string;
    phone: string;
    hours: string;
  };
  locations: ClinicLocation[];
  contactTitle: string;
  contactCards: ContactCard[];
  contactBody: string;
  contactPrimaryCta: string;
  footerCopyright: string;
  socialNavLabel: string;
}
