export type AccidentImage = {
  url: string;
  gps_lat?: number | null;
  gps_lng?: number | null;
  captured_at?: string | null;
};

export type ClaimLocationEntry = {
  captured_at: string | null;
  captured_at_display_local: string | null;
  gps_lat: number | null;
  gps_lng: number | null;
  location_label: string | null;
  location_permission?: string | null;
};

export type ClaimLocations = {
  insurer_call?: ClaimLocationEntry;
  guided_capture_started?: ClaimLocationEntry;
  report_submitted?: ClaimLocationEntry;
};

export type Claim = {
  nic: string;
  customer: string;
  // The claim's exact R2 folder — the real unique id (a claimant can have
  // multiple claims sharing the same nic/customer, each in its own folder).
  folder: string;
  policyId: string;
  vehicleModel: string;
  vehicleRegNo?: string;
  // "YY/MM", e.g. "26/09".
  insuranceExpireMonth?: string;
  submittedDate: string;
  submittedTime: string;
  location: string;
  gpsMatched: boolean;
  timestampSigned: boolean;
  userVerificationAvailable: boolean;
  thirdPartyApplicable: boolean;
  accidentImages: AccidentImage[];
  userVerificationPhotos: AccidentImage[];
  thirdPartyPhotos: AccidentImage[];
  locations?: ClaimLocations;
};
