import './ExploreScreen.css';
import { useTranslation } from 'react-i18next';

interface ExploreScreenProps {
  onStart: () => void;
}

export const ExploreScreen: React.FC<ExploreScreenProps> = ({ onStart }) => {
  const { t } = useTranslation();
  return (
    <main className="explore-screen" aria-labelledby="explore-title">
      <div className="explore-background-lines" aria-hidden="true" />
      <section className="explore-content">
        <h1 id="explore-title">CueVex</h1>
        <div className="explore-subtitle">
          <span />
          <p>{t('app.exploreSubtitle')}</p>
          <span />
        </div>
        <button className="explore-start-button" type="button" onClick={onStart}>
          {t('app.startExplore')}
        </button>
      </section>
    </main>
  );
};

export default ExploreScreen;
