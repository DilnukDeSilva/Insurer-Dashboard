export function DashboardHeader() {
  return (
    <header className="dash-header">
      <div className="dash-header__brand">
        <div className="dash-header__logo" aria-hidden>
        <img
            src="/images/logo.png"
            alt="KADUNA.LK"
            className="dash-header__logo-img"
          />
          {/* <span className="dash-header__logo-text">KADUNA.LK</span> */}
        </div>
        <h1 className="dash-header__title">Intelligent 3D Accident Claim System</h1>
      </div>
      <div className="dash-header__user">
        <span>Hi Janukshan!</span>
        <div className="dash-header__avatar" aria-hidden>
          JS
        </div>
      </div>
    </header>
  );
}
