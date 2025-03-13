import React, { useState, useEffect } from 'react';
import { useKeycloak } from '@react-keycloak/web';

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reportData, setReportData] = useState<any>(null);
  const [hasReportAccess, setHasReportAccess] = useState<boolean>(false);

  // Проверяем наличие роли prothetic_user у пользователя
  useEffect(() => {
    if (initialized && keycloak.authenticated) {
      const hasRole = keycloak.hasRealmRole('prothetic_user');
      setHasReportAccess(hasRole);
    }
  }, [initialized, keycloak.authenticated, keycloak]);

  const downloadReport = async () => {
    if (!keycloak?.token) {
      setError('Не аутентифицирован');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${process.env.REACT_APP_API_URL}/reports`, {
        headers: {
          'Authorization': `Bearer ${keycloak.token}`
        }
      });

      if (!response.ok) {
        if (response.status === 401) {
          setError('Нет доступа к отчетам. Требуется роль prothetic_user.');
        } else if (response.status === 403) {
          setError('Доступ запрещен. Недостаточно прав.');
        } else {
          setError(`Ошибка сервера: ${response.status}`);
        }
        return;
      }

      const data = await response.json();
      setReportData(data);

      // Создаем и скачиваем файл отчета
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'prosthetic-report.json';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Произошла ошибка');
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    keycloak.logout();
  };

  if (!initialized) {
    return <div className="flex justify-center items-center h-screen">Загрузка...</div>;
  }

  if (!keycloak.authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <button
          onClick={() => {
            // Используем параметры PKCE при входе
            keycloak.login();
          }}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Войти
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md w-full max-w-md">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Отчеты об использовании</h1>
          <button 
            onClick={logout}
            className="px-2 py-1 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
          >
            Выйти
          </button>
        </div>
        
        {hasReportAccess ? (
          <button
            onClick={downloadReport}
            disabled={loading}
            className={`w-full px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
              loading ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {loading ? 'Формирование отчета...' : 'Скачать отчет'}
          </button>
        ) : (
          <div className="mt-4 p-4 bg-yellow-100 text-yellow-700 rounded">
            У вас нет доступа к отчетам. Требуется роль prothetic_user.
          </div>
        )}

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">
            {error}
          </div>
        )}
        
        {/* Отображаем информацию о пользователе */}
        <div className="mt-6 p-4 bg-gray-50 rounded border border-gray-200">
          <h2 className="text-lg font-semibold mb-2">Информация о пользователе</h2>
          <p><strong>Имя:</strong> {keycloak.tokenParsed?.preferred_username}</p>
          <p><strong>Роли:</strong> {keycloak.realmAccess?.roles.join(', ')}</p>
        </div>
      </div>
    </div>
  );
};

export default ReportPage;