/**
 * Auraai client config.
 * SmallWebRTC transport: POST /start → POST /sessions/{id}/api/offer (SDP) → PATCH /sessions/{id}/api/offer (ICE candidates).
 * After the PATCH succeeds there are no further HTTP requests—all traffic is over WebRTC (data channel + media).
 * With VITE_BOT_START_PUBLIC_API_KEY set, Bearer token is sent for JWT persistence (run_server.py).
 */

import type { APIRequest } from '@pipecat-ai/client-js';

export type TransportType = 'daily' | 'smallwebrtc';

export const AVAILABLE_TRANSPORTS: TransportType[] = ['smallwebrtc'];

export const TRANSPORT_LABELS: Record<TransportType, string> = {
  daily: 'Daily',
  smallwebrtc: 'SmallWebRTC',
};

export const DEFAULT_TRANSPORT: TransportType = 'smallwebrtc';

const botStartUrl =
  import.meta.env.VITE_BOT_START_URL || 'http://localhost:7860/start';
const botStartPublicApiKey =
  import.meta.env.VITE_BOT_START_PUBLIC_API_KEY?.toString().trim() || '';

if (!import.meta.env.VITE_BOT_START_URL) {
  console.warn(
    'VITE_BOT_START_URL not configured, using default: http://localhost:7860/start'
  );
}

const smallWebRTCConfig: APIRequest = {
  endpoint: botStartUrl,
  requestData: {
    createDailyRoom: false,
    enableDefaultIceServers: true,
    transport: 'webrtc',
  },
  // Allow time for server pipeline (STT/LLM/TTS) to start and send bot-ready
  timeout: 90_000,
};

if (botStartPublicApiKey) {
  smallWebRTCConfig.headers = new Headers({
    Authorization: `Bearer ${botStartPublicApiKey}`,
  });
}

export const TRANSPORT_CONFIG: Record<TransportType, APIRequest> = {
  daily: {
    endpoint: botStartUrl,
    requestData: {
      createDailyRoom: true,
      dailyRoomProperties: { start_video_off: true },
      transport: 'daily',
    },
    ...(botStartPublicApiKey && {
      headers: new Headers({
        Authorization: `Bearer ${botStartPublicApiKey}`,
      }),
    }),
  },
  smallwebrtc: smallWebRTCConfig,
};