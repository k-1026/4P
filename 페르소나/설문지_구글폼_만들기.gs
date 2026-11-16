/**
 * 식당 고르는 방법 설문 — 구글 폼 자동 생성 스크립트
 * 쓰는 법: script.google.com → 새 프로젝트 → 이 코드를 붙여 넣고 저장 → createSurvey 실행 → 권한 허용
 * 실행 로그에 편집 링크 · 응답 링크 · 응답 시트 링크가 나옵니다.
 * 스크립트로 켤 수 없는 설정: 7번 · 10번 "옵션 순서 무작위로 섞기", 13번 "행 순서 무작위로 섞기" → 폼 편집 화면에서 직접 켜기
 * 이름 · 이메일 등 개인정보는 받지 않습니다.
 */
function createSurvey() {
  var form = FormApp.create('식당 고르는 방법 설문 (3분)');
  form.setDescription(
    '안녕하세요. 평소에 식당을 어떻게 고르는지 알아보는 짧은 설문입니다 (3~5분).\n' +
    '대학 수업 팀 프로젝트에 쓰이며, 이름 · 연락처 등 개인을 알 수 있는 정보는 받지 않습니다.\n' +
    '정답은 없으니 평소 하시는 대로 편하게 답해 주세요. 감사합니다!'
  );
  form.setCollectEmail(false);
  form.setProgressBar(true);
  form.setShowLinkToRespondAgain(false);
  form.setConfirmationMessage('응답해 주셔서 감사합니다!');

  // ── 섹션 1. 기본 정보 ──
  form.addSectionHeaderItem().setTitle('1. 기본 정보');

  form.addMultipleChoiceItem()
    .setTitle('1. 나이대')
    .setChoiceValues(['10대', '20대', '30대', '40대', '50대', '60대 이상'])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('2. 지금 사는 곳')
    .setChoiceValues(['대구', '경북', '부산 · 울산 · 경남', '서울 · 경기 · 인천', '그 밖의 지역'])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('3. 대구와의 관계')
    .setChoiceValues(['대구에 살고 있다', '대구 출신이지만 다른 곳에 산다', '대구에 가 본 적이 있다', '대구에 가 본 적이 없다'])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('4. 밖에서 식사(외식)하는 횟수')
    .setChoiceValues(['거의 매일', '일주일에 2~4번', '일주일에 1번', '한 달에 1~3번', '그보다 적게'])
    .setRequired(true);

  form.addCheckboxItem()
    .setTitle('5. 외식할 때 주로 누구와 가나요? (여러 개 가능)')
    .setChoiceValues(['혼자', '친구', '연인', '배우자', '아이', '부모님', '직장 동료'])
    .showOtherOption(true)
    .setRequired(true);

  // ── 섹션 2. 평소 식당 고르는 방법 ──
  form.addPageBreakItem().setTitle('2. 평소 식당 고르는 방법');

  form.addCheckboxItem()
    .setTitle('6. 처음 가 보는 식당을 고를 때 주로 어디서 정보를 얻나요? (여러 개 가능)')
    .setChoiceValues(['네이버 지도 · 플레이스', '카카오맵', '인스타그램', '유튜브', '블로그', '배달앱 리뷰', '지인 추천', '예전에 가 본 곳', '지나가다 보고'])
    .showOtherOption(true)
    .setRequired(true);

  var q7 = form.addCheckboxItem()
    .setTitle('7. 식당을 고를 때 가장 중요하게 보는 것을 최대 3개 골라 주세요')
    .setChoiceValues(['맛 평가', '별점', '리뷰 수', '가격', '거리 · 위치', '메뉴 종류', '분위기 · 인테리어', '기다리는 시간', '주차', '위생 · 청결', '지인 추천', '방송 · SNS에 나온 곳', '오래 영업한 가게', '새로 생긴 가게', '프랜차이즈인지 아닌지', '영업시간'])
    .showOtherOption(true)
    .setRequired(true);
  q7.setValidation(FormApp.createCheckboxValidation()
    .setHelpText('최대 3개까지 골라 주세요')
    .requireSelectAtMost(3)
    .build());

  form.addParagraphTextItem()
    .setTitle('8. 가장 최근에 처음 가 보는 식당을 고른 경험을 떠올려 주세요. 어떻게 골랐나요?')
    .setHelpText('예: 어디서 찾았는지, 무엇을 보고 정했는지 (자유롭게)');

  // ── 섹션 3. 불편했던 점 ──
  form.addPageBreakItem().setTitle('3. 불편했던 점');

  form.addParagraphTextItem()
    .setTitle('9. 식당을 고르거나 가 봤을 때 불편하거나 실망했던 경험이 있다면 한 가지만 적어 주세요')
    .setHelpText('없으면 비워 두셔도 됩니다');

  form.addCheckboxItem()
    .setTitle('10. 아래 중 겪어 본 일을 모두 골라 주세요')
    .setChoiceValues([
      '리뷰 · 별점과 실제 맛이나 양이 달랐다',
      '광고나 협찬 글이 많아 진짜 후기를 구분하기 어려웠다',
      '리뷰 이벤트로 쓴 리뷰가 많아 보였다',
      '줄이 너무 길었다',
      '갔는데 문을 닫았거나 쉬는 날이었다',
      '정보가 너무 많아 고르기 어려웠다',
      '가격이 안내와 달랐다',
      '특별히 없다'
    ])
    .showOtherOption(true)
    .setRequired(true);

  form.addScaleItem()
    .setTitle('11. 식당 리뷰나 별점을 평소 얼마나 믿나요?')
    .setBounds(1, 5)
    .setLabels('전혀 믿지 않는다', '매우 믿는다')
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

  form.addMultipleChoiceItem()
    .setTitle('14. 다른 지역에 놀러 갔을 때 식당 고르는 방법이 평소와 다른가요?')
    .setChoiceValues(['거의 같다', '조금 다르다', '많이 다르다', '다른 지역에 놀러 가지 않는다'])
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle('15. 다르다면 어떻게 다른가요?')
    .setHelpText('없으면 비워 두셔도 됩니다');

  form.addParagraphTextItem()
    .setTitle('16. 그 밖에 식당 고를 때 하고 싶은 말이 있다면')
    .setHelpText('없으면 비워 두셔도 됩니다');

  // 응답을 모을 구글 시트
  var sheet = SpreadsheetApp.create('식당 고르는 방법 설문 응답');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, sheet.getId());

  Logger.log('편집 링크 (팀원만): ' + form.getEditUrl());
  Logger.log('응답 링크 (배포용): ' + form.getPublishedUrl());
  Logger.log('응답 시트: ' + sheet.getUrl());
}
