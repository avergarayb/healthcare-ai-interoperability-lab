package lab.healthcare.fhir.aiconsumerpolicy;

import lab.healthcare.fhir.aiconsumer.AiConsumerContract;

/**
 * Policy input: an existing consumer contract plus synthetic consumer
 * metadata.
 */
public record AiConsumerPolicyInput(AiConsumerContract contract, AiConsumerIdentity consumer) {

    public static AiConsumerPolicyInput of(AiConsumerContract contract, AiConsumerIdentity consumer) {
        return new AiConsumerPolicyInput(contract, consumer);
    }

    public static AiConsumerPolicyInput laboratory(AiConsumerContract contract) {
        return of(contract, AiConsumerIdentity.laboratory());
    }
}
