(() => {
  const form = document.getElementById("patient-form");
  if (!form) return;

  const fields = {
    first_name: document.getElementById("first_name"),
    last_name: document.getElementById("last_name"),
    date_of_birth: document.getElementById("date_of_birth"),
    email: document.getElementById("email"),
    phone: document.getElementById("phone"),
    preferred_language: document.getElementById("preferred_language"),
    preferred_clinic: document.getElementById("preferred_clinic"),
    preferred_date: document.getElementById("preferred_date"),
    preferred_time: document.getElementById("preferred_time"),
    service_type: document.getElementById("service_type"),
    insurance_provider: document.getElementById("insurance_provider"),
    insurance_member_id: document.getElementById("insurance_member_id"),
    patient_id: document.getElementById("patient_id"),
    health_concern: document.getElementById("health_concern"),
    contact_consent: document.getElementById("contact_consent")
  };

  const ui = {
    successMessage: document.getElementById("success_message"),
    patientIdContainer: document.getElementById("patient_id_container"),
    concernCounter: document.getElementById("health_concern_counter"),
    eveningWarning: document.getElementById("evening_warning")
  };

  const baseInputClass = "w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm outline-none transition placeholder:text-slate-500 focus:border-cyan-300 focus:ring-2 focus:ring-cyan-300/40";
  const errorInputClass = "w-full rounded-lg border border-rose-500 bg-slate-950 px-3 py-2.5 text-sm outline-none transition placeholder:text-slate-500 focus:border-rose-400 focus:ring-2 focus:ring-rose-400/40";

  const clinicClosingHour = {
    "HealthCore Austin Central": 20,
    "HealthCore Austin North": 19,
    "HealthCore San Antonio": 18,
    "HealthCore Miami": 20,
    "HealthCore Orlando": 18,
    "HealthCore Atlanta": 19
  };

  const accentLettersRegex = /^[A-Za-zÁÉÍÓÚáéíóúÑñÜü\s]{2,50}$/;
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
  const phoneRegex = /^\+[0-9][0-9\s()-]{6,}$/;
  const memberIdRegex = /^[A-Za-z0-9]{6,20}$/;
  const patientIdRegex = /^HC-[A-Za-z0-9]{6}$/;
  const isSpanish = document.documentElement.lang.toLowerCase().startsWith("es");

  const i18n = {
    firstNameLabel: isSpanish ? "nombre" : "first name",
    lastNameLabel: isSpanish ? "apellido" : "last name",
    firstNameError: isSpanish
      ? "El nombre debe contener solo letras y tener al menos 2 caracteres"
      : "First name must contain letters only and be at least 2 characters long",
    lastNameError: isSpanish
      ? "El apellido debe contener solo letras y tener al menos 2 caracteres"
      : "Last name must contain letters only and be at least 2 characters long",
    dateOfBirthError: isSpanish
      ? "Ingresa una fecha de nacimiento valida. El paciente debe tener entre 0 y 120 anos"
      : "Enter a valid date of birth. The patient must be between 0 and 120 years old",
    emailError: isSpanish
      ? "Ingresa un correo electronico valido (ejemplo: nombre@proveedor.com)"
      : "Enter a valid email address (example: name@provider.com)",
    phoneError: isSpanish
      ? "El telefono debe incluir un codigo de pais (ejemplo: +1 305 555 0191)"
      : "Phone number must include a country code (example: +1 305 555 0191)",
    preferredLanguageError: isSpanish ? "Selecciona tu idioma preferido" : "Select your preferred language",
    preferredClinicError: isSpanish ? "Selecciona la clinica que te gustaria visitar" : "Select the clinic you would like to visit",
    preferredDateError: isSpanish
      ? "Selecciona una fecha de al menos 1 dia habil desde hoy y no mas de 60 dias hacia adelante"
      : "Select a date at least 1 business day from today and no more than 60 days ahead",
    preferredTimeError: isSpanish ? "Selecciona tu franja horaria preferida" : "Select your preferred time window",
    serviceTypeError: isSpanish ? "Selecciona el tipo de atencion que estas buscando" : "Select the type of care you are looking for",
    serviceTypePaediatricError: isSpanish
      ? "Paediatric Care esta disponible para pacientes menores de 18 anos. Revisa la fecha de nacimiento o selecciona un servicio diferente."
      : "Paediatric Care is available for patients under 18. Review the date of birth or select a different service.",
    newPatientError: isSpanish
      ? "Indica si esta es tu primera visita a HealthCore"
      : "Indicate whether this is your first visit to HealthCore",
    hasInsuranceError: isSpanish ? "Indica si tienes seguro medico" : "Indicate whether you have medical insurance",
    insuranceProviderError: isSpanish ? "Ingresa el nombre de tu aseguradora" : "Enter your insurance provider name",
    insuranceMemberIdError: isSpanish
      ? "El ID de afiliado debe tener entre 6 y 20 caracteres alfanumericos"
      : "Member ID must be 6 to 20 alphanumeric characters",
    patientIdError: isSpanish
      ? "El Patient ID debe seguir el formato HC- seguido de 6 caracteres alfanumericos"
      : "Patient ID must match HC- followed by 6 alphanumeric characters",
    concernErrorPrefix: isSpanish
      ? "Describe tu consulta medica en al menos 20 caracteres"
      : "Describe your medical concern in at least 20 characters",
    consentError: isSpanish
      ? "Debes dar tu consentimiento para ser contactado antes de enviar este formulario"
      : "You must provide consent to be contacted before submitting this form",
    eveningWarning: isSpanish
      ? "Advertencia: esta combinacion puede tener disponibilidad limitada para Evening (5pm-8pm)."
      : "Warning: this combination may have limited availability for Evening (5pm-8pm)."
  };

  function getErrorEl(name) {
    return document.getElementById(`${name}_error`);
  }

  function getSelectedRadioValue(name) {
    const selected = form.querySelector(`input[name="${name}"]:checked`);
    return selected ? selected.value : "";
  }

  function setFieldError(name, message) {
    const errorEl = getErrorEl(name);
    if (errorEl) errorEl.textContent = message || "";

    const field = fields[name];
    if (field) {
      field.className = message ? errorInputClass : baseInputClass;
      field.setAttribute("aria-invalid", message ? "true" : "false");
    }

    if (name === "new_patient" || name === "has_insurance") {
      const radios = form.querySelectorAll(`input[name="${name}"]`);
      radios.forEach((radio) => {
        radio.setAttribute("aria-invalid", message ? "true" : "false");
      });
    }

    if (name === "contact_consent") {
      fields.contact_consent.setAttribute("aria-invalid", message ? "true" : "false");
    }

    return !message;
  }

  function toMidnight(date) {
    const copy = new Date(date);
    copy.setHours(0, 0, 0, 0);
    return copy;
  }

  function calculateAge(dateValue) {
    if (!dateValue) return null;
    const today = toMidnight(new Date());
    const birthDate = toMidnight(new Date(dateValue));
    let age = today.getFullYear() - birthDate.getFullYear();
    const monthDiff = today.getMonth() - birthDate.getMonth();
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
      age -= 1;
    }
    return age;
  }

  function addBusinessDays(startDate, businessDays) {
    const date = toMidnight(startDate);
    let added = 0;
    while (added < businessDays) {
      date.setDate(date.getDate() + 1);
      const day = date.getDay();
      if (day !== 0 && day !== 6) added += 1;
    }
    return date;
  }

  function validateName(fieldName, label) {
    const value = fields[fieldName].value.trim();
    if (!accentLettersRegex.test(value)) {
      return setFieldError(fieldName, fieldName === "first_name" ? i18n.firstNameError : i18n.lastNameError);
    }
    return setFieldError(fieldName, "");
  }

  function validateDateOfBirth() {
    const value = fields.date_of_birth.value;
    if (!value) {
      return setFieldError("date_of_birth", i18n.dateOfBirthError);
    }

    const today = toMidnight(new Date());
    const birthDate = toMidnight(new Date(value));
    const age = calculateAge(value);

    const invalid = Number.isNaN(birthDate.getTime()) || birthDate > today || age < 0 || age > 120;
    if (invalid) {
      return setFieldError("date_of_birth", i18n.dateOfBirthError);
    }

    return setFieldError("date_of_birth", "");
  }

  function validateEmail() {
    const value = fields.email.value.trim();
    if (!emailRegex.test(value)) {
      return setFieldError("email", i18n.emailError);
    }
    return setFieldError("email", "");
  }

  function validatePhone() {
    const value = fields.phone.value.trim();
    if (!phoneRegex.test(value)) {
      return setFieldError("phone", i18n.phoneError);
    }
    return setFieldError("phone", "");
  }

  function validateRequiredSelect(name, message) {
    const value = fields[name].value;
    if (!value) {
      return setFieldError(name, message);
    }
    return setFieldError(name, "");
  }

  function validatePreferredDate() {
    const value = fields.preferred_date.value;
    if (!value) {
      return setFieldError("preferred_date", i18n.preferredDateError);
    }

    const selected = toMidnight(new Date(value));
    const today = toMidnight(new Date());
    const minDate = addBusinessDays(today, 1);
    const maxDate = toMidnight(new Date(today));
    maxDate.setDate(maxDate.getDate() + 60);

    const invalid = Number.isNaN(selected.getTime()) || selected < minDate || selected > maxDate;
    if (invalid) {
      return setFieldError("preferred_date", i18n.preferredDateError);
    }

    return setFieldError("preferred_date", "");
  }

  function validateServiceType() {
    const service = fields.service_type.value;
    if (!service) {
      return setFieldError("service_type", i18n.serviceTypeError);
    }

    if (service === "Paediatric Care") {
      const age = calculateAge(fields.date_of_birth.value);
      if (age === null || age >= 18 || age < 0) {
        return setFieldError(
          "service_type",
          i18n.serviceTypePaediatricError
        );
      }
    }

    return setFieldError("service_type", "");
  }

  function validateRadio(name, message) {
    const value = getSelectedRadioValue(name);
    if (!value) {
      return setFieldError(name, message);
    }
    return setFieldError(name, "");
  }

  function validateInsuranceFields() {
    const hasInsurance = getSelectedRadioValue("has_insurance");
    const provider = fields.insurance_provider.value.trim();
    const memberId = fields.insurance_member_id.value.trim();

    let providerValid = true;
    let memberValid = true;

    if (hasInsurance === "Yes") {
      fields.insurance_provider.required = true;
      fields.insurance_member_id.required = true;

      if (!provider) {
        providerValid = setFieldError("insurance_provider", i18n.insuranceProviderError);
      } else {
        providerValid = setFieldError("insurance_provider", "");
      }

      if (!memberIdRegex.test(memberId)) {
        memberValid = setFieldError("insurance_member_id", i18n.insuranceMemberIdError);
      } else {
        memberValid = setFieldError("insurance_member_id", "");
      }
    } else {
      fields.insurance_provider.required = false;
      fields.insurance_member_id.required = false;
      providerValid = setFieldError("insurance_provider", "");
      memberValid = setFieldError("insurance_member_id", "");
    }

    return providerValid && memberValid;
  }

  function togglePatientIdField() {
    const newPatient = getSelectedRadioValue("new_patient");
    const show = newPatient === "No";
    ui.patientIdContainer.classList.toggle("hidden", !show);

    if (!show) {
      fields.patient_id.value = "";
      setFieldError("patient_id", "");
    }
  }

  function validatePatientId() {
    const newPatient = getSelectedRadioValue("new_patient");
    const value = fields.patient_id.value.trim();

    if (newPatient === "No" && value && !patientIdRegex.test(value)) {
      return setFieldError("patient_id", i18n.patientIdError);
    }

    return setFieldError("patient_id", "");
  }

  function validateHealthConcern() {
    const value = fields.health_concern.value.trim();
    const length = value.length;
    ui.concernCounter.textContent = `${length}/500`;

    if (length < 20) {
      const missing = 20 - length;
      const suffix = isSpanish ? `(faltan ${missing} caracteres)` : `(${missing} characters remaining)`;
      return setFieldError("health_concern", `${i18n.concernErrorPrefix} ${suffix}`);
    }

    if (length > 500) {
      const suffix = isSpanish ? "(faltan 0 caracteres)" : "(0 characters remaining)";
      return setFieldError("health_concern", `${i18n.concernErrorPrefix} ${suffix}`);
    }

    return setFieldError("health_concern", "");
  }

  function validateConsent() {
    if (!fields.contact_consent.checked) {
      return setFieldError("contact_consent", i18n.consentError);
    }
    return setFieldError("contact_consent", "");
  }

  function updateEveningWarning() {
    const time = fields.preferred_time.value;
    const clinic = fields.preferred_clinic.value;

    if (time !== "Evening" || !clinic) {
      ui.eveningWarning.textContent = "";
      return;
    }

    const closingHour = clinicClosingHour[clinic];
    if (!closingHour || closingHour <= 18 || closingHour === 19) {
      ui.eveningWarning.textContent = i18n.eveningWarning;
    } else {
      ui.eveningWarning.textContent = "";
    }
  }

  function validateAll() {
    const checks = [
      validateName("first_name", i18n.firstNameLabel),
      validateName("last_name", i18n.lastNameLabel),
      validateDateOfBirth(),
      validateEmail(),
      validatePhone(),
      validateRequiredSelect("preferred_language", i18n.preferredLanguageError),
      validateRequiredSelect("preferred_clinic", i18n.preferredClinicError),
      validatePreferredDate(),
      validateRequiredSelect("preferred_time", i18n.preferredTimeError),
      validateServiceType(),
      validateRadio("new_patient", i18n.newPatientError),
      validateRadio("has_insurance", i18n.hasInsuranceError),
      validateInsuranceFields(),
      validatePatientId(),
      validateHealthConcern(),
      validateConsent()
    ];

    updateEveningWarning();

    return checks.every(Boolean);
  }

  const realtimeValidators = {
    first_name: () => validateName("first_name", i18n.firstNameLabel),
    last_name: () => validateName("last_name", i18n.lastNameLabel),
    date_of_birth: () => {
      validateDateOfBirth();
      validateServiceType();
    },
    email: validateEmail,
    phone: validatePhone,
    preferred_language: () => validateRequiredSelect("preferred_language", i18n.preferredLanguageError),
    preferred_clinic: () => {
      validateRequiredSelect("preferred_clinic", i18n.preferredClinicError);
      updateEveningWarning();
    },
    preferred_date: validatePreferredDate,
    preferred_time: () => {
      validateRequiredSelect("preferred_time", i18n.preferredTimeError);
      updateEveningWarning();
    },
    service_type: validateServiceType,
    insurance_provider: validateInsuranceFields,
    insurance_member_id: validateInsuranceFields,
    patient_id: validatePatientId,
    health_concern: validateHealthConcern,
    contact_consent: validateConsent
  };

  Object.keys(realtimeValidators).forEach((name) => {
    const field = fields[name];
    if (!field) return;

    const eventType = field.tagName === "SELECT" || field.type === "checkbox" ? "change" : "input";
    field.addEventListener(eventType, realtimeValidators[name]);
    field.addEventListener("blur", realtimeValidators[name]);
  });

  form.querySelectorAll('input[name="new_patient"]').forEach((radio) => {
    radio.addEventListener("change", () => {
      validateRadio("new_patient", i18n.newPatientError);
      togglePatientIdField();
      validatePatientId();
    });
  });

  form.querySelectorAll('input[name="has_insurance"]').forEach((radio) => {
    radio.addEventListener("change", () => {
      validateRadio("has_insurance", i18n.hasInsuranceError);
      validateInsuranceFields();
    });
  });

  form.addEventListener("reset", () => {
    window.setTimeout(() => {
      Object.keys(fields).forEach((name) => {
        const field = fields[name];
        if (!field) return;

        if (field.tagName === "INPUT" || field.tagName === "SELECT" || field.tagName === "TEXTAREA") {
          field.setAttribute("aria-invalid", "false");
        }

        if (["first_name", "last_name", "date_of_birth", "email", "phone", "preferred_language", "preferred_clinic", "preferred_date", "preferred_time", "service_type", "insurance_provider", "insurance_member_id", "patient_id", "health_concern"].includes(name)) {
          field.className = baseInputClass;
        }

        setFieldError(name, "");
      });

      ui.concernCounter.textContent = "0/500";
      ui.eveningWarning.textContent = "";
      ui.successMessage.classList.add("hidden");
      ui.patientIdContainer.classList.add("hidden");
    }, 0);
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    ui.successMessage.classList.add("hidden");

    const valid = validateAll();
    if (!valid) {
      const firstError = form.querySelector('[aria-invalid="true"]');
      if (firstError) firstError.focus();
      return;
    }

    ui.successMessage.classList.remove("hidden");
    ui.successMessage.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  // Initial UI state
  togglePatientIdField();
  ui.concernCounter.textContent = "0/500";
})();
