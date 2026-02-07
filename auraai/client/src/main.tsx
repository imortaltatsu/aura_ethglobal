import { StrictMode, useState } from 'react';
import { createRoot } from 'react-dom/client';

import { ThemeProvider } from '@pipecat-ai/voice-ui-kit';

import type { PipecatBaseChildProps } from '@pipecat-ai/voice-ui-kit';
import {
  ErrorCard,
  FullScreenContainer,
  PipecatAppBase,
  SpinLoader,
} from '@pipecat-ai/voice-ui-kit';

import { App } from './components/App';
import {
  isRegistered,
  RegisterScreen,
} from './components/RegisterScreen';
import {
  AVAILABLE_TRANSPORTS,
  DEFAULT_TRANSPORT,
  TRANSPORT_CONFIG,
} from './config';
import type { TransportType } from './config';
import './index.css';

export const Main = () => {
  const [transportType, setTransportType] =
    useState<TransportType>(DEFAULT_TRANSPORT);
  const [showRegister, setShowRegister] = useState(!isRegistered());

  const connectParams = TRANSPORT_CONFIG[transportType];

  if (showRegister) {
    return (
      <ThemeProvider defaultTheme="terminal" disableStorage>
        <RegisterScreen
          onRegistered={() => setShowRegister(false)}
          onSkip={() => setShowRegister(false)}
        />
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider defaultTheme="terminal" disableStorage>
      <FullScreenContainer>
        <PipecatAppBase
          connectParams={connectParams}
          startBotParams={connectParams}
          transportType={transportType}
          initDevicesOnMount
          clientOptions={{ enableCam: false, enableMic: true }}
        >
          {({
            client,
            handleConnect,
            handleDisconnect,
            error,
          }: PipecatBaseChildProps) =>
            !client ? (
              <SpinLoader />
            ) : error ? (
              <ErrorCard>{error}</ErrorCard>
            ) : (
              <App
                client={client}
                handleConnect={handleConnect}
                handleDisconnect={handleDisconnect}
                transportType={transportType}
                onTransportChange={setTransportType}
                availableTransports={AVAILABLE_TRANSPORTS}
              />
            )
          }
        </PipecatAppBase>
      </FullScreenContainer>
    </ThemeProvider>
  );
};

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Main />
  </StrictMode>
);
