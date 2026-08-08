import { useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";

const API_BASE = import.meta.env.VITE_API_URL ?? "";
const PATIENT_ID = "SYNTHETIC-001";
const CAREGIVER_ID = "CG-001";
const DEMO_HEADERS = { "X-Caregiver-Id": CAREGIVER_ID };
const DISCLAIMER =
  "Synthetic demonstration system - not affiliated with HealthHub, MOH or any healthcare institution. All patients and records are fictional.";
const FACILITY_OPTIONS = ["CarePortal General Hospital", "CarePortal Community Clinic", "CarePortal Specialist Centre"];
const DEPARTMENT_OPTIONS = ["Cardiology", "Geriatric Medicine", "Physiotherapy", "General Medicine"];

type Section =
  | "home"
  | "appointments"
  | "registration"
  | "records"
  | "medications"
  | "bills"
  | "notifications"
  | "profiles";

type ApiError = { message: string; status?: number };

type Appointment = {
  id: string;
  patientId: string;
  facility: string;
  department: string;
  datetime: string;
  previousDatetime: string | null;
  status: string;
  instructions: string[];
  lastUpdated: string;
  changeHistory: Array<Record<string, string>>;
  isSynthetic: boolean;
};

type NotificationItem = {
  id: string;
  category: string;
  title: string;
  message: string;
  relatedResourceId: string | null;
  createdAt: string;
  isRead: boolean;
  actionRequired: boolean;
  priority: string;
  isSynthetic: boolean;
};

type Overview = {
  patient: { id: string; name: string; age: number; isSynthetic: boolean };
  authorizedCaregiver: { id: string; name: string; relationship: string };
  nextAppointment: Appointment | null;
  recentNotifications: NotificationItem[];
  outstandingAdministrativeActions: NotificationItem[];
  medicationRefillStatus: { displayName?: string; refillStatus?: string; status?: string; remainingRefills?: number };
  outstandingBillSummary: { restricted: boolean; outstandingCount: number | null; message: string };
  isSynthetic: boolean;
};

type Slot = {
  id: string;
  appointmentId: string;
  department: string;
  facility: string;
  datetime: string;
  available: boolean;
  isSynthetic: boolean;
};

type DocumentItem = {
  id: string;
  documentType: string;
  facility: string;
  specialty: string;
  documentDate: string;
  lastUpdated: string;
  sampleContent: string;
  isSynthetic: boolean;
};

type Medication = {
  id: string;
  displayName: string;
  prescribedInstruction: string;
  refillStatus: string;
  remainingRefills: number;
  prescribingFacility: string;
  lastUpdated: string;
  isSynthetic: boolean;
};

type RefillRequest = {
  id: string;
  medicationId: string;
  displayName: string;
  status: string;
  collectionOptions: string[];
  lastUpdated: string;
  isSynthetic: boolean;
};

type Bill = {
  id: string;
  facility: string;
  serviceDate: string;
  amount: string;
  paymentStatus: string;
  dueDate: string;
  isSynthetic: boolean;
};

type Profile = {
  id: string;
  displayName: string;
  relationship: string;
  profileType: string;
  accessStatus: string;
  isSynthetic: boolean;
};

type HealthProfiles = {
  activeProfileId: string;
  loggedInUser: { id: string; name: string; relationship: string };
  profiles: Profile[];
  accessSummary: { status: string; items: string[]; note: string };
  isSynthetic: boolean;
};

type VisitRegistration = {
  visits: Array<{
    id: string;
    appointmentId: string;
    facility: string;
    department: string;
    datetime: string;
    registrationStatus: string;
    queueNumber: string | null;
    canRegister: boolean;
    registrationWindow: string;
    message: string;
  }>;
  isSynthetic: boolean;
};

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        ...DEMO_HEADERS,
        "Content-Type": "application/json",
        ...(options.headers ?? {})
      }
    });
    if (!response.ok) {
      let message = response.statusText;
      try {
        const body = await response.json();
        message = body.detail ?? message;
      } catch {
        // Use the status text if the backend did not return JSON.
      }
      throw { message, status: response.status } satisfies ApiError;
    }
    return response.json();
  } catch (error) {
    if (error instanceof TypeError) {
      throw { message: "Portal service is offline. Start the backend on 127.0.0.1:8000." } satisfies ApiError;
    }
    throw error;
  }
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "Not recorded";
  return new Intl.DateTimeFormat("en-SG", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Singapore"
  }).format(new Date(value));
}

function label(value: string | null | undefined) {
  if (!value) return "";
  const known: Record<string, string> = {
    may_be_due: "May be due",
    not_open: "Not open",
    care_recipient: "Care recipient",
    family_caregiver: "Family caregiver",
    appointment_rescheduled: "Appointment rescheduled",
    ready_to_request: "Ready to request"
  };
  if (known[value]) return known[value];
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function dateInputValue(daysFromToday = 14) {
  const date = new Date();
  date.setDate(date.getDate() + daysFromToday);
  return date.toISOString().slice(0, 10);
}

function initials(value: string) {
  return value
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function Badge({ value, tone }: { value: string; tone?: "good" | "warn" | "danger" | "muted" }) {
  return <span className={`badge ${tone ?? "muted"}`}>{label(value)}</span>;
}

function Empty({ children }: { children: string }) {
  return <div className="empty">{children}</div>;
}

function Loading() {
  return <div className="loading">Loading records...</div>;
}

function ErrorBox({ error }: { error: ApiError | null }) {
  if (!error) return null;
  return (
    <div role="alert" className="error">
      {error.status ? `${error.status}: ` : ""}
      {error.message}
    </div>
  );
}

function ServiceButton({ children, disabled = true }: { children: ReactNode; disabled?: boolean }) {
  return (
    <button className="secondary" disabled={disabled}>
      {children}
    </button>
  );
}

function App() {
  const [section, setSection] = useState<Section>("home");
  const nav = useMemo(
    () =>
      [
        ["home", "Home"],
        ["appointments", "Appointments"],
        ["registration", "Visit Registration"],
        ["records", "Health Records"],
        ["medications", "Medications"],
        ["bills", "Bills"],
        ["notifications", "Notifications"],
        ["profiles", "Health Profiles"]
      ] as Array<[Section, string]>,
    []
  );

  return (
    <div className="shell">
      <aside className="sidebar" aria-label="Primary">
        <div>
          <p className="eyebrow">Age Well Hackathon</p>
          <h1>CarePortal Sandbox</h1>
          <p className="subtitle">Health services demo for Mr Jia.</p>
        </div>
        <div className="profile-switcher" aria-label="Current profile">
          <span>Viewing profile</span>
          <strong>Mr Jia Sijia</strong>
          <small>Care recipient of Huang Tian</small>
        </div>
        <nav>
          {nav.map(([key, label]) => (
            <button key={key} className={section === key ? "active" : ""} onClick={() => setSection(key)}>
              {label}
            </button>
          ))}
        </nav>
      </aside>

      <main>
        <div className="disclaimer" role="note">
          {DISCLAIMER}
        </div>
        {section === "home" && <Dashboard onNavigate={setSection} />}
        {section === "appointments" && <Appointments />}
        {section === "registration" && <VisitRegistrationPage />}
        {section === "records" && <Documents />}
        {section === "medications" && <Medications />}
        {section === "bills" && <Bills />}
        {section === "notifications" && <Notifications />}
        {section === "profiles" && <Profiles />}
      </main>
    </div>
  );
}

function Dashboard({ onNavigate }: { onNavigate: (section: Section) => void }) {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    api<Overview>(`/api/patients/${PATIENT_ID}/overview`).then(setOverview).catch(setError);
  }, []);

  if (error) return <ErrorBox error={error} />;
  if (!overview) return <Loading />;

  return (
    <section>
      <div className="page-title">
        <div>
          <h2>Home</h2>
          <p>{overview.authorizedCaregiver.name} viewing {overview.patient.name}</p>
        </div>
        <Badge value="profile" tone="good" />
      </div>

      <div className="metrics">
        <article className="panel">
          <span>Next appointment</span>
          <strong>{overview.nextAppointment?.department ?? "None"}</strong>
          <p>{formatDateTime(overview.nextAppointment?.datetime)}</p>
          {overview.nextAppointment && <Badge value={overview.nextAppointment.status} tone="warn" />}
        </article>
        <article className="panel">
          <span>Mobile registration</span>
          <strong>Not open</strong>
          <p>Available before visit time.</p>
        </article>
        <article className="panel">
          <span>Medication refill</span>
          <strong>{overview.medicationRefillStatus.displayName ?? "Current"}</strong>
          <p>{label(overview.medicationRefillStatus.refillStatus ?? overview.medicationRefillStatus.status)}</p>
        </article>
        <article className="panel">
          <span>Bills</span>
          <strong>{overview.outstandingBillSummary.outstandingCount ?? 0} outstanding</strong>
          <p>{overview.outstandingBillSummary.message}</p>
        </article>
      </div>

      <div className="split">
        <article className="panel">
          <h3>Recent Notifications</h3>
          {overview.recentNotifications.length === 0 ? (
            <Empty>No recent notifications.</Empty>
          ) : (
            <ul className="list">
              {overview.recentNotifications.map((item) => (
                <li key={item.id}>
                  <div>
                    <strong>{item.title}</strong>
                    <p>{item.message}</p>
                  </div>
                  <Badge value={item.priority} tone={item.priority === "high" ? "danger" : "warn"} />
                </li>
              ))}
            </ul>
          )}
        </article>
        <article className="panel">
          <h3>Services</h3>
          <div className="quick-links">
            <button onClick={() => onNavigate("appointments")}>Appointments</button>
            <button onClick={() => onNavigate("registration")}>Visit registration</button>
            <button onClick={() => onNavigate("medications")}>Medication refill</button>
            <button onClick={() => onNavigate("bills")}>View bills</button>
          </div>
        </article>
      </div>
    </section>
  );
}

function Appointments() {
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [selectedId, setSelectedId] = useState("APT-001");
  const [detail, setDetail] = useState<Appointment | null>(null);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [selectedSlot, setSelectedSlot] = useState<Slot | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const [bookingOpen, setBookingOpen] = useState(false);
  const [bookingFacility, setBookingFacility] = useState(FACILITY_OPTIONS[0]);
  const [bookingDepartment, setBookingDepartment] = useState(DEPARTMENT_OPTIONS[0]);
  const [bookingDate, setBookingDate] = useState(dateInputValue());
  const [bookingBusy, setBookingBusy] = useState(false);
  const [cancelBusy, setCancelBusy] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    setError(null);
    Promise.all([
      api<{ appointments: Appointment[] }>(`/api/patients/${PATIENT_ID}/appointments`),
      api<Appointment>(`/api/appointments/${selectedId}`)
    ])
      .then(async ([appointmentList, appointmentDetail]) => {
        const slotList =
          appointmentDetail.department === "Cardiology" && appointmentDetail.status !== "cancelled"
            ? await api<{ slots: Slot[] }>(`/api/appointments/${selectedId}/available-slots`)
            : { slots: [] };
        setAppointments(appointmentList.appointments);
        setDetail(appointmentDetail);
        setSlots(slotList.slots);
        setSelectedSlot(null);
      })
      .catch((err: ApiError) => setError(err))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
  }, [selectedId]);

  async function confirmReschedule() {
    if (!selectedSlot || !detail) return;
    setError(null);
    try {
      const response = await api<{ appointment: Appointment; message: string }>(`/api/appointments/${detail.id}/reschedule`, {
        method: "POST",
        body: JSON.stringify({ slotId: selectedSlot.id, reason: "Caregiver portal request" })
      });
      setSuccess(`${response.message} ${formatDateTime(detail.datetime)} to ${formatDateTime(response.appointment.datetime)}.`);
      setConfirming(false);
      setSelectedSlot(null);
      load();
    } catch (err) {
      setError(err as ApiError);
    }
  }

  async function bookAppointment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBookingBusy(true);
    setError(null);
    try {
      const response = await api<{ appointment: Appointment; message: string }>(`/api/patients/${PATIENT_ID}/appointments`, {
        method: "POST",
        body: JSON.stringify({
          facility: bookingFacility,
          department: bookingDepartment,
          date: bookingDate,
          reason: "Caregiver portal booking"
        })
      });
      setSuccess(`${response.message} ${response.appointment.department} at ${response.appointment.facility} on ${formatDateTime(response.appointment.datetime)}.`);
      setBookingOpen(false);
      setSelectedId(response.appointment.id);
      setSelectedSlot(null);
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setBookingBusy(false);
    }
  }

  async function cancelAppointment() {
    if (!detail) return;
    setCancelBusy(true);
    setError(null);
    try {
      const response = await api<{ appointment: Appointment; message: string }>(`/api/appointments/${detail.id}/cancel`, {
        method: "POST"
      });
      setSuccess(`${response.message} ${response.appointment.department} at ${response.appointment.facility}.`);
      setConfirmingCancel(false);
      setDetail(response.appointment);
      load();
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setCancelBusy(false);
    }
  }

  if (loading && !detail) return <Loading />;

  const canReschedule = detail?.department === "Cardiology" && detail.status !== "cancelled";
  const canCancel = Boolean(detail && detail.department !== "Cardiology" && detail.status !== "cancelled");

  return (
    <section>
      <div className="page-title">
        <div>
          <h2>Appointments</h2>
          <p>Upcoming visits for Mr Jia.</p>
        </div>
        <button className="secondary" onClick={load}>Refresh</button>
      </div>
      <ErrorBox error={error} />
      {success && <div className="success">{success}</div>}

      <div className="appointment-layout">
        <article className="panel appointment-list">
          <h3>Appointments</h3>
          <div className="appointment-cards">
            {appointments.map((appointment) => (
              <button
                key={appointment.id}
                className={selectedId === appointment.id ? "appointment-card selected" : "appointment-card"}
                onClick={() => setSelectedId(appointment.id)}
              >
                <span>{formatDateTime(appointment.datetime)}</span>
                <strong>{appointment.department}</strong>
                <small>{appointment.facility}</small>
                <Badge value={appointment.status} tone={appointment.status === "confirmed" ? "good" : appointment.status === "cancelled" ? "danger" : "warn"} />
              </button>
            ))}
          </div>
          <div className="actions service-actions">
            <button className="primary" onClick={() => setBookingOpen((value) => !value)}>
              Book Appointment
            </button>
            <ServiceButton>Request</ServiceButton>
          </div>
          {bookingOpen && (
            <form className="booking-form" onSubmit={bookAppointment}>
              <label>
                <span>Institution</span>
                <select value={bookingFacility} onChange={(event) => setBookingFacility(event.target.value)}>
                  {FACILITY_OPTIONS.map((facility) => (
                    <option key={facility} value={facility}>{facility}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Service</span>
                <select value={bookingDepartment} onChange={(event) => setBookingDepartment(event.target.value)}>
                  {DEPARTMENT_OPTIONS.map((department) => (
                    <option key={department} value={department}>{department}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Date</span>
                <input type="date" min={dateInputValue(0)} value={bookingDate} onChange={(event) => setBookingDate(event.target.value)} />
              </label>
              <button className="primary" disabled={bookingBusy || !bookingDate}>
                {bookingBusy ? "Booking..." : "Confirm Booking"}
              </button>
            </form>
          )}
        </article>

        {detail && (
          <article className="panel detail">
            <div className="detail-head">
              <div>
                <h3>{detail.department}</h3>
                <p>{detail.facility}</p>
              </div>
              <Badge value={detail.status} tone={detail.status === "confirmed" ? "good" : detail.status === "cancelled" ? "danger" : "warn"} />
            </div>
            <dl>
              <dt>Current date and time</dt>
              <dd>{formatDateTime(detail.datetime)}</dd>
              <dt>Previous date and time</dt>
              <dd>{formatDateTime(detail.previousDatetime)}</dd>
              <dt>Last updated</dt>
              <dd>{formatDateTime(detail.lastUpdated)}</dd>
            </dl>
            <h4>Preparation Instructions</h4>
            <ul className="bullets">{detail.instructions.map((item) => <li key={item}>{item}</li>)}</ul>
            {detail.previousDatetime && (
              <div className="notice">
                Moved from {formatDateTime(detail.previousDatetime)}
              </div>
            )}
            {canReschedule && (
              <div className="reschedule-box">
                <div className="detail-head">
                  <div>
                    <h4>Choose a New Time</h4>
                    <p>Only available slots are shown.</p>
                  </div>
                </div>
                <div className="slots" role="list">
                  {slots.length === 0 ? (
                    <Empty>No available slots right now.</Empty>
                  ) : (
                    slots.map((slot) => (
                      <button
                        key={slot.id}
                        className={selectedSlot?.id === slot.id ? "slot selected" : "slot"}
                        onClick={() => setSelectedSlot(slot)}
                      >
                        <strong>{formatDateTime(slot.datetime)}</strong>
                        <small>{slot.facility}</small>
                      </button>
                    ))
                  )}
                </div>
              </div>
            )}
            <div className="actions">
              {canReschedule && (
                <button className="primary" disabled={!selectedSlot} onClick={() => setConfirming(true)}>
                  Review Reschedule
                </button>
              )}
              {canCancel && (
                <button className="secondary danger-action" onClick={() => setConfirmingCancel(true)}>
                  Cancel Appointment
                </button>
              )}
            </div>
          </article>
        )}
      </div>

      {confirming && detail && selectedSlot && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
            <h3 id="confirm-title">Confirm Reschedule</h3>
            <p>From {formatDateTime(detail.datetime)}</p>
            <p>To {formatDateTime(selectedSlot.datetime)}</p>
            <div className="actions">
              <button className="secondary" onClick={() => setConfirming(false)}>Cancel</button>
              <button className="primary" onClick={confirmReschedule}>Confirm</button>
            </div>
          </div>
        </div>
      )}

      {confirmingCancel && detail && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="cancel-title">
            <h3 id="cancel-title">Cancel Appointment</h3>
            <p>{detail.department}</p>
            <p>{formatDateTime(detail.datetime)}</p>
            <div className="actions">
              <button className="secondary" onClick={() => setConfirmingCancel(false)}>Keep Appointment</button>
              <button className="secondary danger-action" disabled={cancelBusy} onClick={cancelAppointment}>
                {cancelBusy ? "Cancelling..." : "Confirm Cancel"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function VisitRegistrationPage() {
  const [data, setData] = useState<VisitRegistration | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    api<VisitRegistration>(`/api/patients/${PATIENT_ID}/visit-registration`).then(setData).catch(setError);
  }, []);

  return (
    <ReadOnlySection title="Visit Registration" error={error} badge="check-in">
      {!data ? <Loading /> : data.visits.length === 0 ? <Empty>No upcoming visits available.</Empty> : data.visits.map((visit) => (
        <article className="panel compact" key={visit.id}>
          <div className="detail-head">
            <h3>{visit.department}</h3>
            <Badge value={visit.registrationStatus} tone="warn" />
          </div>
          <p>{visit.facility}</p>
          <p>{formatDateTime(visit.datetime)}</p>
          <p>{visit.message}</p>
          <p>{visit.registrationWindow}</p>
          <p>Queue: {visit.queueNumber ?? "Not issued"}</p>
          <button className="primary" disabled={!visit.canRegister}>Register for visit</button>
        </article>
      ))}
    </ReadOnlySection>
  );
}

function Documents() {
  const [items, setItems] = useState<DocumentItem[]>([]);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    api<{ documents: DocumentItem[] }>(`/api/patients/${PATIENT_ID}/documents`).then((body) => setItems(body.documents)).catch(setError);
  }, []);

  return (
    <section>
      <div className="page-title">
        <div>
          <h2>Health Records</h2>
          <p>Documents and results for Mr Jia.</p>
        </div>
      </div>
      <ErrorBox error={error} />
      {items.length === 0 && !error ? (
        <Loading />
      ) : (
        <article className="panel">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Record</th>
                  <th>Specialty</th>
                  <th>Institution</th>
                  <th>Date</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <strong>{item.documentType}</strong>
                      <p>{item.id}</p>
                    </td>
                    <td>{item.specialty}</td>
                    <td>{item.facility}</td>
                    <td>{item.documentDate}</td>
                    <td>
                      <div className="actions service-actions">
                        <button className="secondary" disabled>View</button>
                        <button className="secondary" disabled>Download</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      )}
    </section>
  );
}

function Medications() {
  const [items, setItems] = useState<Medication[]>([]);
  const [refills, setRefills] = useState<RefillRequest[]>([]);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    Promise.all([
      api<{ medications: Medication[] }>(`/api/patients/${PATIENT_ID}/medications`),
      api<{ requests: RefillRequest[] }>(`/api/patients/${PATIENT_ID}/medication-refills`)
    ])
      .then(([medicationBody, refillBody]) => {
        setItems(medicationBody.medications);
        setRefills(refillBody.requests);
      })
      .catch((err: ApiError) => setError(err));
  }, []);

  return (
    <section>
      <div className="page-title">
        <div>
          <h2>Medications</h2>
          <p>Current medication records for Mr Jia.</p>
        </div>
      </div>
      <ErrorBox error={error} />
      {items.length === 0 && !error ? (
        <Loading />
      ) : (
        <>
          <article className="panel">
            <h3>Medication List</h3>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Medicine</th>
                    <th>Institution</th>
                    <th>Instruction</th>
                    <th>Refills</th>
                    <th>Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <strong>{item.displayName}</strong>
                      </td>
                      <td>{item.prescribingFacility}</td>
                      <td>{item.prescribedInstruction}</td>
                      <td>
                        <Badge value={item.refillStatus} tone={item.refillStatus === "current" ? "good" : "warn"} />
                        <p>{item.remainingRefills} remaining</p>
                      </td>
                      <td>{formatDateTime(item.lastUpdated)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>

          {refills.length > 0 && (
            <article className="panel refill-alert">
              <div>
                <h3>Refill Attention</h3>
                <p>{refills[0].displayName} may be ready for a refill request.</p>
              </div>
              <Badge value={refills[0].status} tone="warn" />
              <button className="primary" disabled>Request refill</button>
            </article>
          )}
        </>
      )}
    </section>
  );
}

function Bills() {
  const [items, setItems] = useState<Bill[]>([]);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    api<{ bills: Bill[] }>(`/api/patients/${PATIENT_ID}/bills`).then((body) => setItems(body.bills)).catch(setError);
  }, []);

  const outstanding = items.filter((item) => item.paymentStatus === "outstanding");

  return (
    <section>
      <div className="page-title">
        <div>
          <h2>Bills</h2>
          <p>Outstanding and paid bills.</p>
        </div>
        <Badge value={`${outstanding.length} outstanding`} tone={outstanding.length ? "warn" : "good"} />
      </div>
      <ErrorBox error={error} />
      {items.length === 0 && !error ? <Loading /> : (
        <div className="grid-list">
          {items.map((item) => (
            <article className="panel compact" key={item.id}>
              <div className="detail-head">
                <h3>{item.id}</h3>
                <Badge value={item.paymentStatus} tone={item.paymentStatus === "paid" ? "good" : "warn"} />
              </div>
              <p>{item.facility}</p>
              <p>Service date: {item.serviceDate}</p>
              <p>Amount: {item.amount}</p>
              <p>Due date: {item.dueDate}</p>
              <div className="actions service-actions">
                <button className="secondary" disabled>Download</button>
                <button className="primary" disabled>{item.paymentStatus === "paid" ? "Receipt available" : "Pay"}</button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function Notifications() {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [error, setError] = useState<ApiError | null>(null);

  function load() {
    api<{ notifications: NotificationItem[] }>(`/api/patients/${PATIENT_ID}/notifications`)
      .then((body) => setItems(body.notifications))
      .catch((err: ApiError) => setError(err));
  }

  useEffect(() => {
    load();
  }, []);

  async function markRead(id: string) {
    await api<NotificationItem>(`/api/notifications/${id}/read`, { method: "PATCH" });
    load();
  }

  return (
    <section>
      <div className="page-title">
        <div>
          <h2>Notifications</h2>
          <p>Profile updates and reminders.</p>
        </div>
      </div>
      <ErrorBox error={error} />
      {items.length === 0 && !error ? <Loading /> : (
        <ul className="list card-list">
          {items.map((item) => (
            <li key={item.id}>
              <div>
                <strong>{item.title}</strong>
                <p>{item.message}</p>
                <span>{formatDateTime(item.createdAt)}</span>
              </div>
              <div className="row-actions">
                {item.actionRequired && <Badge value="action required" tone="danger" />}
                <Badge value={item.isRead ? "read" : "unread"} tone={item.isRead ? "muted" : "warn"} />
                {!item.isRead && <button className="secondary" onClick={() => markRead(item.id)}>Mark Read</button>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Profiles() {
  const [data, setData] = useState<HealthProfiles | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    api<HealthProfiles>(`/api/patients/${PATIENT_ID}/health-profiles`).then(setData).catch(setError);
  }, []);

  const activeProfile = data?.profiles.find((profile) => profile.id === data.activeProfileId);
  const loggedInProfile = data?.profiles.find((profile) => profile.id === data.loggedInUser.id);
  const familyProfiles = data?.profiles.filter((profile) => profile.id !== data.activeProfileId && profile.id !== data.loggedInUser.id) ?? [];

  return (
    <section>
      <div className="page-title">
        <div>
          <h2>Health Profiles</h2>
          <p>Profile access for Huang Tian and Mr Jia.</p>
        </div>
      </div>
      <ErrorBox error={error} />
      {!data ? <Loading /> : (
        <>
          <div className="profile-overview">
            <article className="panel current-profile">
              <span className="section-label">Viewing now</span>
              <div className="profile-hero">
                <div className="avatar large">{initials(activeProfile?.displayName ?? "")}</div>
                <div>
                  <h3>{activeProfile?.displayName}</h3>
                  <p>{activeProfile?.relationship}</p>
                </div>
              </div>
              <div className="profile-meta">
                <div>
                  <span>Access</span>
                  <strong>{data.accessSummary.status.replace("demo ", "")}</strong>
                </div>
                <div>
                  <span>Managed by</span>
                  <strong>{data.loggedInUser.name}</strong>
                </div>
              </div>
            </article>

            <article className="panel signed-in-profile">
              <span className="section-label">Logged in as</span>
              <div className="profile-row">
                <div className="avatar">{initials(loggedInProfile?.displayName ?? data.loggedInUser.name)}</div>
                <div>
                  <strong>{data.loggedInUser.name}</strong>
                  <p>{data.loggedInUser.relationship}</p>
                </div>
              </div>
              <Badge value="Caregiver access" tone="good" />
            </article>
          </div>

          <div className="profile-layout">
            <article className="panel">
              <div className="detail-head">
                <h3>Linked Profiles</h3>
                <Badge value={`${data.profiles.length} profiles`} tone="muted" />
              </div>
              <div className="profile-list">
                {data.profiles.map((profile) => (
                  <div className={profile.id === data.activeProfileId ? "profile-row active" : "profile-row"} key={profile.id}>
                    <div className="avatar">{initials(profile.displayName)}</div>
                    <div>
                      <strong>{profile.displayName}</strong>
                      <p>{profile.relationship}</p>
                    </div>
                    <Badge
                      value={profile.id === data.activeProfileId ? "Viewing" : profile.id === data.loggedInUser.id ? "Signed in" : "Linked"}
                      tone={profile.id === data.activeProfileId ? "good" : "muted"}
                    />
                  </div>
                ))}
              </div>
            </article>

            <article className="panel">
              <h3>Huang Tian Can Help With</h3>
              <div className="access-grid">
                {data.accessSummary.items.map((item) => (
                  <span key={item}>{item}</span>
                ))}
              </div>
            </article>
          </div>

          {familyProfiles.length > 0 && (
            <article className="panel profile-summary">
              <h3>Family Caregivers</h3>
              <div className="profile-list compact-list">
                {familyProfiles.map((profile) => (
                  <div className="profile-row" key={profile.id}>
                    <div className="avatar">{initials(profile.displayName)}</div>
                    <div>
                      <strong>{profile.displayName}</strong>
                      <p>{profile.relationship}</p>
                    </div>
                    <Badge value="On record" tone="muted" />
                  </div>
                ))}
              </div>
            </article>
          )}
        </>
      )}
    </section>
  );
}

function ReadOnlySection({ title, error, badge, children }: { title: string; error: ApiError | null; badge: string; children: ReactNode }) {
  return (
    <section>
      <div className="page-title">
        <div>
          <h2>{title}</h2>
        </div>
        <Badge value={badge} tone="muted" />
      </div>
      <ErrorBox error={error} />
      <div className="grid-list">{children}</div>
    </section>
  );
}

export default App;
