/**
 * 식당 고르는 방법 설문 v3 — 구글 폼 자동 생성 스크립트 (설문지_식당고르기_v3.md와 같은 문항)
 * 쓰는 법: script.google.com → 새 프로젝트 → 이 코드를 붙여 넣고 저장 → createSurvey 실행 → 권한 허용
 * 실행 로그에 편집 링크 · 응답 링크 · 응답 시트 링크가 나옵니다.
 * 스크립트로 켤 수 없는 설정 (폼 편집 화면에서 직접 켜기):
 *   6번 · 9번 · 14번 "옵션 순서 무작위로 섞기", 13번 · 15번 "행 순서 무작위로 섞기"
 * 이름 · 이메일 등 개인정보는 받지 않습니다.
 */
function createSurvey() {
  var form = FormApp.create('식당 고르는 방법 설문 (3분)');
  form.setDescription(
    '안녕하세요. 평소에 식당을 어떻게 고르는지 알아보는 짧은 설문입니다 (3분).\n' +
    '대학 수업 팀 프로젝트에 쓰이며, 이름 · 연락처 등 개인을 알 수 있는 정보는 받지 않습니다.\n' +
    '정답은 없으니 평소 하시는 대로 편하게 답해 주세요. 쓰는 칸은 안 써도 괜찮아요. 감사합니다!'
  );
  form.setCollectEmail(false);
  form.setProgressBar(true);
  form.setShowLinkToRespondAgain(false);
  form.setConfirmationMessage('응답해 주셔서 감사합니다!');

  // ── 섹션 1. 기본 정보 ──
  form.addSectionHeaderItem().setTitle('1. 기본 정보');

  form.addMultipleChoiceItem()
    .setTitle('1. 나이대')
    .setChoiceValues(['10대', '20대', '30대 초반', '30대 중반', '30대 후반', '40대', '50대', '60대 이상'])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('2. 지금 사는 곳')
    .setChoiceValues(['대구', '경북', '부산 · 울산 · 경남', '서울 · 경기 · 인천', '그 밖의 지역'])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('3. 대구와의 관계')
    .setChoiceValues(['대구에 살고 있다', '대구 출신이지만 다른 곳에 산다', '대구에 가 본 적이 있다', '대구에 가 본 적이 없다'])
    .setRequired(true);

  form.addCheckboxItem()
    .setTitle('4. 외식할 때 주로 누구와 가나요? (여러 개 가능)')
    .setChoiceValues(['혼자', '친구', '연인', '배우자', '아이', '부모님', '직장 동료'])
    .showOtherOption(true)
    .setRequired(true);

  // ── 섹션 2. 처음 가 보는 동네에서 식당 고르기 ──
  form.addPageBreakItem().setTitle('2. 처음 가 보는 동네에서 식당 고르기');

  form.addCheckboxItem()
    .setTitle('5. 처음 가 보는 동네에서 식당을 고를 때 주로 어디서 정보를 얻나요? (여러 개 가능)')
    .setChoiceValues(['네이버 지도 · 플레이스', '카카오맵', '인스타그램', '유튜브', '블로그', '배달앱 리뷰', '지인 추천', '예전에 가 본 곳', '지나가다 보고'])
    .showOtherOption(true)
    .setRequired(true);

  var q6 = form.addCheckboxItem()
    .setTitle('6. 처음 가 보는 동네에서 식당을 고를 때 가장 중요하게 보는 것을 최대 3개 골라 주세요')
    .setChoiceValues(['맛 평가', '별점', '리뷰 수', '가격', '거리 · 위치', '메뉴 종류', '분위기 · 인테리어', '기다리는 시간', '주차', '위생 · 청결', '지인 추천', '방송 · SNS에 나온 곳', '오래 영업한 가게', '새로 생긴 가게', '프랜차이즈인지 아닌지', '영업시간'])
    .showOtherOption(true)
    .setRequired(true);
  q6.setValidation(FormApp.createCheckboxValidation()
    .setHelpText('최대 3개까지 골라 주세요')
    .requireSelectAtMost(3)
    .build());

  form.addParagraphTextItem()
    .setTitle('7. 가장 최근에 낯선 동네에서 처음 가 보는 식당을 고른 경험을 떠올려 주세요. 어떻게 골랐나요?')
    .setHelpText('예: 어디서 찾았는지, 무엇을 보고 정했는지 (자유롭게, 안 써도 돼요)');

  // ── 섹션 3. 불편했던 점 ──
  form.addPageBreakItem().setTitle('3. 불편했던 점');

  form.addParagraphTextItem()
    .setTitle('8. 식당을 고르거나 가 봤을 때 불편하거나 실망했던 경험이 있다면 한 가지만 한 줄로 적어 주세요')
    .setHelpText('안 써도 돼요');

  form.addCheckboxItem()
    .setTitle('9. 아래 중 겪어 본 일을 모두 골라 주세요')
    .setChoiceValues([
      '리뷰 · 별점과 실제 맛이나 양이 달랐다',
      '광고나 협찬 글이 많아 진짜 후기를 구분하기 어려웠다',
      '리뷰 이벤트로 쓴 리뷰가 많아 보였다',
      '줄이 너무 길었다',
      '갔는데 문을 닫았거나 쉬는 날이었다',
      '정보가 너무 많아 고르기 어려웠다',
      '가격이 안내와 달랐다',
      '일정이 빠듯해서 식당 고르는 데 시간을 쓰기 어려웠다',
      '특별히 없다'
    ])
    .showOtherOption(true)
    .setRequired(true);

  form.addScaleItem()
    .setTitle('10. 식당 리뷰나 별점을 평소 얼마나 믿나요?')
    .setBounds(1, 5)
    .setLabels('전혀 믿지 않는다', '매우 믿는다')
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('11. 최근 1년 동안, 리뷰나 별점을 보고 골랐는데 기대와 달랐던 적이 몇 번쯤 있나요?')
    .setChoiceValues(['한 번도 없다', '1~2번', '3~5번', '6번 이상'])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('12. "리뷰 쓰면 음료 서비스" 같은 리뷰 이벤트를 보면, 그 가게 별점을 어떻게 받아들이나요?')
    .setChoiceValues(['더 믿게 된다', '별 차이 없다', '덜 믿게 된다', '본 적이 없거나 잘 모르겠다'])
    .setRequired(true);

  // ── 섹션 4. 정보에 대한 생각 ──
  form.addPageBreakItem().setTitle('4. 정보에 대한 생각');

  form.addGridItem()
    .setTitle('13. 식당을 고를 때 아래 정보가 있다면 얼마나 도움이 될까요?')
    .setRows(['방문자 리뷰', '별점', '가격대', '지금 영업 중인지 (폐업 · 휴무 여부)', '기다리는 시간', '그 자리에서 영업한 기간', '위생 점검 결과'])
    .setColumns(['전혀 도움 안 됨', '별로', '보통', '도움 됨', '매우 도움 됨'])
    .setRequired(true);

  var q14 = form.addCheckboxItem()
    .setTitle('14. 리뷰나 별점을 믿기 어렵다고 느꼈을 때, 대신 무엇을 보나요? 가까운 것 최대 2개')
    .setChoiceValues(['지인 추천', '예전에 가 본 곳', '오래 영업한 가게', '줄 서는 곳', '사진', '가격', '그냥 리뷰를 본다', '믿기 어렵다고 느낀 적이 없다'])
    .showOtherOption(true)
    .setRequired(true);
  q14.setValidation(FormApp.createCheckboxValidation()
    .setHelpText('최대 2개까지 골라 주세요')
    .requireSelectAtMost(2)
    .build());

  form.addGridItem()
    .setTitle('15. 식당 정보에 아래처럼 적혀 있다면, 고를 때 참고할 것 같나요?')
    .setRows(['"이 자리에서 23년째 영업 중"', '"이 자리에서 6개월째 영업 중"'])
    .setColumns(['꼭 참고한다', '참고할 듯', '별로', '전혀'])
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle('16. 그 밖에 식당 고를 때 하고 싶은 말이 있다면 (예: 15번에서 그렇게 답한 이유)')
    .setHelpText('안 써도 돼요');

  // 응답을 모을 구글 시트
  var sheet = SpreadsheetApp.create('식당 고르는 방법 설문 응답');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, sheet.getId());

  Logger.log('편집 링크 (팀원만): ' + form.getEditUrl());
  Logger.log('응답 링크 (배포용): ' + form.getPublishedUrl());
  Logger.log('응답 시트: ' + sheet.getUrl());
}
