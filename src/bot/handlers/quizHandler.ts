import { Telegraf } from 'telegraf';
import { CustomContext } from '../../types/context';
import { Direction } from '../../types/lead';
import { messages, getDirectionLabel } from '../messages';
import { quizDirectionKeyboard, quizAnswerKeyboard } from '../keyboards/quiz';
import { buildQuizSummary, getPrimaryQuestion, getFollowUpQuestion } from '../states/quizMachine';
import { withCallbackGuard } from '../../utils/callbackGuard';

export const registerQuizHandlers = (bot: Telegraf<CustomContext>) => {
  bot.action(
    'srvt:quiz:start:main',
    withCallbackGuard(async (ctx) => {
      ctx.session.flow = 'quiz';
      ctx.session.quiz = { stage: 'primary', answers: {} };
      await ctx.reply(messages.quizIntro, quizDirectionKeyboard());
    })
  );

  bot.action(
    /^srvt:quiz:direction:(?<direction>[a-z_]+)/,
    withCallbackGuard(async (ctx) => {
      const direction = (ctx.match?.groups?.direction as Direction) ?? 'other';
      ctx.session.flow = 'quiz';
      ctx.session.quiz = { direction, stage: 'primary', answers: {} };
      const question = getPrimaryQuestion(direction);
      await ctx.reply(
        messages.quizQuestion(question.text),
        quizAnswerKeyboard(question.key, question.options)
      );
    })
  );

  bot.action(
    /^srvt:quiz:answer:(?<payload>.+)/,
    withCallbackGuard(async (ctx) => {
      const quizState = ctx.session.quiz;
      if (!quizState?.direction) {
        await ctx.reply('Сначала выберите направление из меню.');
        return;
      }

      const payload = ctx.match?.groups?.payload;
      if (!payload) {
        return;
      }
      const [questionKey, value] = payload.split('__');
      if (!value) {
        return;
      }

      const stage = quizState.stage ?? 'primary';
      const question =
        stage === 'primary'
          ? getPrimaryQuestion(quizState.direction)
          : getFollowUpQuestion(quizState.direction);

      if (!question || question.key !== questionKey) {
        return;
      }

      quizState.answers[question.key] = value;

      if (stage === 'primary') {
        const followUp = getFollowUpQuestion(quizState.direction);
        if (followUp) {
          quizState.stage = 'followup';
          await ctx.reply(
            messages.quizQuestion(followUp.text),
            quizAnswerKeyboard(followUp.key, followUp.options)
          );
          return;
        }
      }

      quizState.stage = 'done';
      const summary = buildQuizSummary(quizState.direction, value);
      const directionLabel = getDirectionLabel(quizState.direction);

      ctx.session.lastQuiz = {
        direction: quizState.direction,
        summary,
        answers: quizState.answers
      };
      ctx.session.flow = 'idle';

      await ctx.replyWithMarkdown(messages.quizSummary(directionLabel, summary));
      await ctx.replyWithMarkdown(
        messages.quizClosing(quizState.direction, summary),
        {
          reply_markup: {
            inline_keyboard: [
              [{ text: messages.quizCta, callback_data: 'srvt:lead:start:quiz' }],
              [{ text: 'Вернуться в меню', callback_data: 'srvt:menu:open:root' }]
            ]
          }
        }
      );
    })
  );
};



