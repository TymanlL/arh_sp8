import React from 'react';
import { ReactKeycloakProvider } from '@react-keycloak/web';
import Keycloak, { KeycloakConfig } from 'keycloak-js';
import ReportPage from './components/ReportPage';

// Утилита для генерации случайной строки для code_verifier
const generateRandomString = (length: number): string => {
  const charset = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~';
  let result = '';
  for (let i = 0; i < length; i++) {
    const randomIndex = Math.floor(Math.random() * charset.length);
    result += charset[randomIndex];
  }
  return result;
};

// Функция для вычисления code_challenge из code_verifier
const generateCodeChallenge = async (codeVerifier: string): Promise<string> => {
  // Преобразуем строку в массив байтов
  const encoder = new TextEncoder();
  const data = encoder.encode(codeVerifier);
  
  // Создаем хеш SHA-256
  const hash = await crypto.subtle.digest('SHA-256', data);
  
  // Преобразуем результат в base64-url формат
  const hashArray = Array.from(new Uint8Array(hash));
  const hashString = hashArray.map(b => String.fromCharCode(b)).join('');
  let base64 = btoa(hashString);
  
  // Трансформируем base64 в base64url
  return base64
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
};

// Генерируем code_verifier и сохраняем его в localStorage
const setupPKCE = async (): Promise<{codeVerifier: string, codeChallenge: string}> => {
  const codeVerifier = generateRandomString(128);
  const codeChallenge = await generateCodeChallenge(codeVerifier);
  
  // Сохраняем code_verifier для последующей проверки
  localStorage.setItem('codeVerifier', codeVerifier);
  
  return { codeVerifier, codeChallenge };
};

const keycloakConfig: KeycloakConfig = {
  url: process.env.REACT_APP_KEYCLOAK_URL,
  realm: process.env.REACT_APP_KEYCLOAK_REALM || "",
  clientId: process.env.REACT_APP_KEYCLOAK_CLIENT_ID || ""
};

const keycloak = new Keycloak(keycloakConfig);

const App: React.FC = () => {
  // Настраиваем PKCE перед инициализацией Keycloak
  const pkceEnabled = true;
  
  // Настраиваем опции инициализации
  const initOptions = {
    pkceMethod: 'S256',
    onLoad: 'check-sso',
    // Добавляем code_challenge параметры
    checkLoginIframe: false
  };

  const handleOnEvent = async (event: string) => {
    if (event === 'onAuthLogin') {
      // При логине, если нужно предпринять дополнительные действия
      console.log('Authentication successful');
    }
  };

  // Обработка успешной авторизации
  const handleTokens = async (tokens: any) => {
    // Здесь можно сохранить токены или выполнить другие действия
    console.log('Received tokens:', tokens);
  };

  return (
    <ReactKeycloakProvider 
      authClient={keycloak}
      initOptions={initOptions}
      onEvent={handleOnEvent}
      onTokens={handleTokens}
    >
      <div className="App">
        <ReportPage />
      </div>
    </ReactKeycloakProvider>
  );
};

export default App;