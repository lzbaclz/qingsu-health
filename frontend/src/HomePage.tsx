import { Link } from 'react-router-dom'

export default function HomePage() {
  return (
    <div className="home">
      <header className="home-head">
        <div className="brand brand-lg">体迹 AI</div>
        <p className="home-tagline">面向专科门诊的 AI 症状表达与病程协作工具</p>
        <p className="small muted">原型演示 · 数据均为模拟，非真实患者 · 不做诊断，不提供治疗或用药建议</p>
      </header>
      <div className="home-cards">
        <Link to="/p" className="home-card">
          <div className="home-card-kicker">患者端 · 手机</div>
          <h2>就诊前把症状说清楚</h2>
          <p>身体地图 + 用自己的话描述；系统按临床协议补问，最后由你确认记录是否准确。</p>
          <span className="btn btn-primary">进入患者端</span>
        </Link>
        <Link to="/d" className="home-card">
          <div className="home-card-kicker">医生端 · 桌面</div>
          <h2>带出处的摘要与变化</h2>
          <p>摘要、矛盾、缺口、红旗任务，每条事实可回溯原话；随访时看到"相比上次变了什么"。</p>
          <span className="btn btn-secondary">进入医生端</span>
        </Link>
      </div>
      <p className="small muted center">模型整理原话和复述差异；问什么、何时升级，由临床协议决定并交医护核实。</p>
    </div>
  )
}
