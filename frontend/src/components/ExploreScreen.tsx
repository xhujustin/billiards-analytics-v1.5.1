import './ExploreScreen.css';

interface ExploreScreenProps {
  onStart: () => void;
}

export const ExploreScreen: React.FC<ExploreScreenProps> = ({ onStart }) => {
  return (
    <main className="explore-screen" aria-labelledby="explore-title">
      <div className="explore-background-lines" aria-hidden="true" />
      <section className="explore-content">
        <h1 id="explore-title">Q Track</h1>
        <div className="explore-subtitle">
          <span />
          <p>BILLIARDS ANALYSIS SYSTEM</p>
          <span />
        </div>
        <button className="explore-start-button" type="button" onClick={onStart}>
          開始探索
        </button>
      </section>
    </main>
  );
};

export default ExploreScreen;
