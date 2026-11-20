/**
 * 식당 고르기 설문 (1분 · 체크만) — 구글 폼 자동 생성
 * 쓰는 법: script.google.com → 새 프로젝트 → 붙여 넣고 저장 → createSurvey 실행 → 권한 허용
 * 실행 로그에 편집 · 응답 · 응답 시트 링크가 나옵니다.
 * 직접 켤 것: 6 · 7 · 9번 "옵션 순서 무작위로 섞기" (스크립트로는 안 됨)
 * 개인정보(이름 · 이메일)는 받지 않습니다.
 */
function createSurvey() {
  var form = FormApp.create('식당 고르기 설문 (1분)');
  form.setDescription('식당 고르는 방법을 묻는 1분 설문이에요. 고르기만 하면 돼요.\n수업 팀 프로젝트용 · 익명 · 개인정보 받지 않음. 감사합니다!');
  form.setCollectEmail(false);
  form.setShowLinkToRespondAgain(false);
  form.setConfirmationMessage('감사합니다!');

  form.addMultipleChoiceItem().setTitle('1. 나이')
    .setChoiceValues(['10대', '20대', '30대', '40대', '50대 이상']).setRequired(true);

  form.addMultipleChoiceItem().setTitle('2. 사는 곳')
    .setChoiceValues(['대구', '경북', '부산 · 울산 · 경남', '수도권', '그 밖']).setRequired(true);

  form.addMultipleChoiceItem().setTitle('3. 본가가 대구인가요?')
    .setChoiceValues(['예', '아니오']).setRequired(true);

  form.addCheckboxItem().setTitle('4. 외식은 주로 누구와? (여러 개)')
    .setChoiceValues(['혼자', '친구', '연인', '배우자', '아이', '가족(부모님)', '직장 동료']).setRequired(true);

  form.addCheckboxItem().setTitle('5. 식당 정보는 어디서? (여러 개)')
    .setChoiceValues(['네이버', '카카오맵', '인스타', '유튜브', '블로그', '지인', '예전에 가 본 곳', '지나가다']).setRequired(true);

  var q5 = form.addCheckboxItem().setTitle('6. 고를 때 가장 중요한 것 (최대 3개)')
    .setChoiceValues(['맛 평가', '별점', '리뷰 수', '가격', '거리', '분위기', '대기 시간', '위생', '지인 추천', 'SNS · 방송', '오래된 가게', '새로 생긴 가게', '영업시간'])
    .setRequired(true);
  q5.setValidation(FormApp.createCheckboxValidation().setHelpText('최대 3개').requireSelectAtMost(3).build());

  form.addCheckboxItem().setTitle('7. 겪어 본 일 (모두)')
    .setChoiceValues(['리뷰와 실제가 달랐다', '광고 글이 많아 헷갈렸다', '리뷰 이벤트 리뷰가 많았다', '줄이 너무 길었다', '갔는데 문을 닫았다', '특별히 없다'])
    .setRequired(true);

  form.addScaleItem().setTitle('8. 리뷰 · 별점, 얼마나 믿어요?')
    .setBounds(1, 5).setLabels('전혀 안 믿음', '매우 믿음').setRequired(true);

  var q8 = form.addCheckboxItem().setTitle('9. 있으면 좋을 정보 (최대 2개)')
    .setChoiceValues(['진짜 방문자 리뷰', '가격대', '지금 영업 중인지', '대기 시간', '그 자리에서 영업한 기간', '위생 점검 결과'])
    .setRequired(true);
  q8.setValidation(FormApp.createCheckboxValidation().setHelpText('최대 2개').requireSelectAtMost(2).build());

  var sheet = SpreadsheetApp.create('식당 고르기 설문 응답');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, sheet.getId());

  Logger.log('편집 링크 (팀원만): ' + form.getEditUrl());
  Logger.log('응답 링크 (배포용): ' + form.getPublishedUrl());
  Logger.log('응답 시트: ' + sheet.getUrl());
}
