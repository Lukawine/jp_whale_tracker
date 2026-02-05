import re
from fuzzywuzzy import fuzz

class AnnouncementGrader:
    def __init__(self):
        # 1. 基于正则的关键词评分规则
        # 【S级】顶级价值 (必须第一时间推送)
        self.patterns_s = [
            r'上方修正', r'増配', r'自己株式取得', r'株式分割', r'株主優待制度の導入', r'特別利益'
        ]
        # 【A级】核心进展 (具有博弈价值)
        self.patterns_a = [
            r'業務提携', r'契約締結', r'量産', r'ライセンス許諾', r'新製品', 
            r'共同開発', r'受注', r'事業譲受', r'中期経営計画', 
            r'ライセンス許諾', r'新規事業', r'子会社化'
        ]
        # 【D级】利空风险 (预警或做空建议)
        self.patterns_d = [
            r'下方修正', r'減配', r'赤字', r'損失', r'延期', r'中止', r'特別損失',r'債務超過'
        ]
        # 【E级】无意义/噪音
        self.patterns_e = [
            r'人事異動', r'定款一部変更', r'組織変更', r'役員の異動', r'公益財団法人', r'ガバナンス',
            r'定款一部変更', r'支配株主等に関する事項', r'法定事後開示書類'
        ]
        
        # 【Noise】假利好/噪音 (强制降级)
        self.patterns_noise = [
            r'影響は軽微', r'検討開始', r'金額は未定', r'今期業績への影響は未定', r'意向表明'
        ]
        self.keywords_s = [s.replace(r'上方修正', '') for s in self.patterns_s]
        self.keywords_a = [a.replace(r'業務提携', '') for a in self.patterns_a]
        self.keywords_d = [d.replace(r'下方修正', '') for d in self.patterns_d]

        # 2. 模拟波动率数据 (Volatility Map)
        # 在实际生产中，这里应该连接金融数据库或 API
        self.volatility_map = {
            '9984': 0.45, # Softbank Group (High Volatility)
            '7203': 0.25, # Toyota (Medium)
            '8031': 0.20, # Mitsui (Low)
            '3853': 0.50, # Infoteria (High)
        }

    def _get_volatility(self, stock_code):
        """获取股票的历史波动率，默认为 0.30"""
        return self.volatility_map.get(stock_code, 0.30)

    def extract_key_action(self, title):
        """
        使用 re.search 提取括弧内的关键动作。
        例如: "XXに関するお知らせ（上方修正）" -> "上方修正"
        """
        # 匹配圆括号 () 或全角圆括号 （） 或方括号 []
        match = re.search(r'[（\(\[](.*?)[\)\）\]]', title)
        if match:
            return match.group(1)
        return title # 如果没有括号，返回原标题

    def calculate_grade(self, stock_code, title):
        """
        综合计算评级、分数和敏感度
        """
        grade = 'C' # 默认为中性
        score = 50
        
        # 关键词匹配优先级: S > D > A > E; 使用模糊匹配
        if any(fuzz.partial_ratio(p, title) > 90 for p in self.patterns_s):
            grade = 'S'; score = 95
        elif any(fuzz.partial_ratio(p, title) > 90 for p in self.patterns_d):
            grade = 'D'; score = 30
        elif any(fuzz.partial_ratio(p, title) > 90 for p in self.patterns_a):
            grade = 'A'; score = 80
        elif any(re.search(p, title) for p in self.patterns_e):
            grade = 'E'; score = 10 # E级不做模糊匹配
        
        # Noise Filter Override (Title)
        if any(re.search(p, title) for p in self.patterns_noise):
            grade = 'D'; score = 30
            
        # 波动率敏感度分析
        volatility = self._get_volatility(stock_code)
        sensitivity = "Normal"
        if volatility >= 0.40:
            sensitivity = "High"
        elif volatility <= 0.20:
            sensitivity = "Low"
            
        return {
            'grade': grade,
            'score': score,
            'sensitivity': sensitivity,
            'key_action': self.extract_key_action(title)
        }

    def check_noise(self, text):
        """Checks text for noise patterns."""
        if not text:
            return False
        return any(re.search(p, text) for p in self.patterns_noise)

# 实例化以便直接导入使用
grader = AnnouncementGrader()