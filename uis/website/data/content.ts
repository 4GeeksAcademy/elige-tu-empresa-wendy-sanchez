import { WebsiteContent } from "@/types/website";

const baseLocations = [
  {
    name: "HealthCore Austin Central",
    city: "Austin",
    state: "TX",
    phone: "(512) 340-8800",
    hours: "Mon-Fri 7am-8pm | Sat 9am-3pm",
    hoursEs: "Lun-Vie 7am-8pm | Sab 9am-3pm",
    schemaHours: "Mo-Fr 07:00-20:00, Sa 09:00-15:00",
  },
  {
    name: "HealthCore Austin North",
    city: "Austin",
    state: "TX",
    phone: "(512) 340-8810",
    hours: "Mon-Fri 8am-7pm",
    hoursEs: "Lun-Vie 8am-7pm",
    schemaHours: "Mo-Fr 08:00-19:00",
  },
  {
    name: "HealthCore San Antonio",
    city: "San Antonio",
    state: "TX",
    phone: "(210) 720-4400",
    hours: "Mon-Fri 8am-6pm | Sat 9am-1pm",
    hoursEs: "Lun-Vie 8am-6pm | Sab 9am-1pm",
    schemaHours: "Mo-Fr 08:00-18:00, Sa 09:00-13:00",
  },
  {
    name: "HealthCore Miami",
    city: "Miami",
    state: "FL",
    phone: "(305) 510-7700",
    hours: "Mon-Fri 7am-8pm | Sat 9am-4pm",
    hoursEs: "Lun-Vie 7am-8pm | Sab 9am-4pm",
    schemaHours: "Mo-Fr 07:00-20:00, Sa 09:00-16:00",
  },
  {
    name: "HealthCore Orlando",
    city: "Orlando",
    state: "FL",
    phone: "(407) 892-6600",
    hours: "Mon-Fri 8am-6pm",
    hoursEs: "Lun-Vie 8am-6pm",
    schemaHours: "Mo-Fr 08:00-18:00",
  },
  {
    name: "HealthCore Atlanta",
    city: "Atlanta",
    state: "GA",
    phone: "(404) 330-9900",
    hours: "Mon-Fri 8am-7pm",
    hoursEs: "Lun-Vie 8am-7pm",
    schemaHours: "Mo-Fr 08:00-19:00",
  },
] as const;

export const englishContent: WebsiteContent = {
  lang: "en",
  title: "HealthCore | Outpatient Healthcare Services",
  description:
    "HealthCore is an outpatient healthcare network with 12 clinics across the US and UK, offering same-day appointments, extended hours, and bilingual care.",
  navLabel: "Main navigation",
  mobileNavLabel: "Mobile navigation",
  homeAnchor: "home",
  homeAriaLabel: "HealthCore home",
  navItems: [
    { label: "Home", href: "#home" },
    { label: "Services", href: "#services" },
    { label: "Locations", href: "#locations" },
    { label: "Contact", href: "#contact" },
  ],
  heroBadge: "Outpatient Healthcare Network",
  heroTitle: "Healthcare that adapts to your life",
  heroSubtitle:
    "12 outpatient clinics across the US and UK offering same-day appointments, extended hours, and bilingual care, so you can get the care you need when you need it.",
  heroPrimaryCta: "Request an appointment",
  heroSecondaryCta: "Explore services",
  heroImageAlt: "Health professional assisting a patient in an outpatient clinic",
  servicesTitle: "Services",
  servicesSubtitle:
    "Comprehensive ambulatory services designed for prevention, continuity, and specialist support.",
  services: [
    {
      title: "Primary Care and Chronic Disease Management",
      bullets: [
        "Same-day appointments with primary care physicians",
        "Ongoing management for diabetes, hypertension, and asthma",
      ],
    },
    {
      title: "Specialist Consultations",
      bullets: [
        "Cardiology, endocrinology, pulmonology, and women's health",
        "Coordinated referrals within the HealthCore network",
      ],
    },
    {
      title: "Preventive Health and Wellness",
      bullets: [
        "Check-ups, vaccination, and annual screenings",
        "Mental health counseling and psychiatry referrals",
      ],
    },
  ],
  whyTitle: "Why HealthCore",
  whyItems: [
    { emphasis: "Same-day appointments", text: "in most locations" },
    {
      emphasis: "Extended hours",
      text: "weekday service until 7pm or 8pm, with Saturday availability",
    },
    {
      emphasis: "Bilingual staff",
      text: "in English and Spanish across US locations",
    },
    { emphasis: "12 clinics", text: "in Texas, Florida, Georgia, and the UK" },
  ],
  whyCardTitle: "Built for modern patient access",
  whyCardBody:
    "HealthCore combines clínical excellence with practical accessibility: quick availability, coordinated care pathways, and patient-first communication in the languages your family speaks every day.",
  whyCardCta: "Go to patient inquiry form",
  locationsTitle: "US Locations",
  locationsNote:
    "UK clinics serve an independent market and are not included on this public website.",
  locationsTableLabel: "HealthCore US clinics table",
  locationsColumns: {
    clinic: "Clinic name",
    city: "City",
    state: "State",
    phone: "Phone",
    hours: "Hours",
  },
  locations: baseLocations.map((location) => ({
    name: location.name,
    city: location.city,
    state: location.state,
    phone: location.phone,
    hours: location.hours,
    schemaHours: location.schemaHours,
  })),
  contactTitle: "Contact",
  contactCards: [
    { title: "General inquiries", value: "info@healthcore.com" },
    { title: "Austin HQ", value: "(512) 340-8800" },
    { title: "Miami", value: "(305) 510-7700" },
    { title: "United Kingdom (London)", value: "+44 20 7946 0100" },
  ],
  contactBody:
    "Looking to book care? Use our structured patient inquiry form and our reception team will contact you within one business day.",
  contactPrimaryCta: "Open patient inquiry form",
  footerCopyright: "© 2025 HealthCore. All rights reserved.",
  socialNavLabel: "Social medía",
};

export const spanishContent: WebsiteContent = {
  lang: "es",
  title: "HealthCore | Servicios de Salud Ambulatorios",
  description:
    "HealthCore es una red de salud ambulatoria con 12 clínicas en EE. UU. y Reino Unido, con citas el mismo día, horarios extendidos y atención bilingüe.",
  navLabel: "Navegación principal",
  mobileNavLabel: "Navegación móvil",
  homeAnchor: "inicio",
  homeAriaLabel: "Inicio de HealthCore",
  navItems: [
    { label: "Inicio", href: "#inicio" },
    { label: "Servicios", href: "#servicios" },
    { label: "Ubicaciones", href: "#ubicaciones" },
    { label: "Contacto", href: "#contacto" },
  ],
  heroBadge: "Red de Salud Ambulatoria",
  heroTitle: "Atención médica que se adapta a tu vida",
  heroSubtitle:
    "12 clínicas ambulatorias en EE. UU. y Reino Unido que ofrecen citas el mismo día, horarios extendidos y atención bilingüe, para que recibas la atención que necesitas, cuando la necesitas.",
  heroPrimaryCta: "Solicitar una cita",
  heroSecondaryCta: "Ver servicios",
  heroImageAlt: "Profesional de la salud asistiendo a una paciente en una clínica ambulatoria",
  servicesTitle: "Servicios",
  servicesSubtitle:
    "Servicios ambulatorios integrales diseñados para prevención, continuidad y apoyo especializado.",
  services: [
    {
      title: "Atención Primaria y Enfermedades Crónicas",
      bullets: [
        "Citas el mismo día con médicos de atención primaria",
        "Manejo continuo de diabetes, hipertensión y asma",
      ],
    },
    {
      title: "Consultas con Especialistas",
      bullets: [
        "Cardiología, endocrinología, neumología y salud de la mujer",
        "Derivaciones coordinadas dentro de la red de HealthCore",
      ],
    },
    {
      title: "Salud Preventiva y Bienestar",
      bullets: [
        "Chequeos, vacunación y revisiones anuales",
        "Asesoramiento en salud mental y derivaciones a psiquiatría",
      ],
    },
  ],
  whyTitle: "Por qué HealthCore",
  whyItems: [
    { emphasis: "Citas el mismo día", text: "en la mayoría de las ubicaciones" },
    {
      emphasis: "Horarios extendidos",
      text: "entre semana hasta las 7pm u 8pm, sábados disponibles",
    },
    {
      emphasis: "Personal bilingüe",
      text: "en inglés y español en ubicaciones de EE. UU.",
    },
    { emphasis: "12 clínicas", text: "en Texas, Florida, Georgia y el Reino Unido" },
  ],
  whyCardTitle: "Diseñado para el acceso moderno de pacientes",
  whyCardBody:
    "HealthCore combina excelencia clínica con accesibilidad real: disponibilidad rápida, rutas de atención coordinadas y comunicación centrada en el paciente en los idiomas que usa tu familia cada día.",
  whyCardCta: "Ir al formulario de consulta",
  locationsTitle: "Ubicaciones en EE. UU.",
  locationsNote:
    "Las clínicas del Reino Unido atienden un mercado independiente y no se incluyen en este sitio web público.",
  locationsTableLabel: "Tabla de clínicas de HealthCore en Estados Unidos",
  locationsColumns: {
    clinic: "Nombre de la clínica",
    city: "Ciudad",
    state: "Estado",
    phone: "Teléfono",
    hours: "Horario",
  },
  locations: baseLocations.map((location) => ({
    name: location.name,
    city: location.city,
    state: location.state,
    phone: location.phone,
    hours: location.hoursEs,
    schemaHours: location.schemaHours,
  })),
  contactTitle: "Contacto",
  contactCards: [
    { title: "Consultas generales", value: "info@healthcore.com" },
    { title: "Sede central de Austin", value: "(512) 340-8800" },
    { title: "Miami", value: "(305) 510-7700" },
    { title: "Reino Unido (Londres)", value: "+44 20 7946 0100" },
  ],
  contactBody:
    "¿Quieres solicitar atención? Usa nuestro formulario de consulta para pacientes y recepción se pondrá en contacto contigo dentro de 1 día hábil.",
  contactPrimaryCta: "Abrir formulario de consulta",
  footerCopyright: "© 2025 HealthCore. Todos los derechos reservados.",
  socialNavLabel: "Redes sociales",
};
